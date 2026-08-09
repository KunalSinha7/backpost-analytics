"""Phase 1 identity: external-id normalization, the resolver, and the backfill.

The Marseille case runs through most of these. StatsBomb's match feed calls
team 147 "Olympique de Marseille" while its event feed calls it "Marseille",
and every bug this phase fixes is some version of treating those as two teams.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from app.models.player import Player
from app.models.position import Position
from app.models.team import Team, TeamAlias
from app.services.identity_backfill import (
    EmptyBackfillInputError,
    IdentityBackfillService,
)
from app.services.resolver import EntityResolver, normalize_external_id
from tests.utils.soccer import (
    create_competition,
    create_event,
    create_lineup,
    create_match,
)

MARSEILLE_ID = 147
MATCH_FEED_NAME = "Olympique de Marseille"
EVENT_FEED_NAME = "Marseille"


# ── normalize_external_id ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # The case that matters: pandas widens any column containing a null to
        # float64, so ids come back as float strings from some feeds and plain
        # ints from others — in the same payload.
        ("3348.0", "3348"),
        (3348.0, "3348"),
        (147, "147"),
        ("147", "147"),
        ("  147  ", "147"),
        # Non-numeric ids pass through: other sources use uuids and slugs.
        ("abc-123", "abc-123"),
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_normalize_external_id(raw: object, expected: str | None) -> None:
    assert normalize_external_id(raw) == expected


def test_normalize_external_id_agrees_with_sql_cast(db: Session) -> None:
    """The Python and SQL canonicalisations must produce the same string.

    The resolver writes `team.external_id` in Python; the backfill matches it
    with ::numeric::bigint::text in SQL. If the two disagree, the UPDATE joins
    nothing, updates zero rows, and reports success — a silent no-op rather
    than an error. This pins them together.
    """
    for raw in ("3348.0", "147", "0", "99999"):
        via_sql = db.execute(
            text("SELECT (:v)::numeric::bigint::text"), {"v": raw}
        ).scalar_one()
        assert normalize_external_id(raw) == via_sql


# ── EntityResolver ──────────────────────────────────────────────────────────


def test_resolver_keys_on_id_not_name(db: Session) -> None:
    """Two spellings of one id must produce exactly one team."""
    resolver = EntityResolver(db)
    first = resolver.resolve_team(MARSEILLE_ID, MATCH_FEED_NAME)
    second = resolver.resolve_team(MARSEILLE_ID, EVENT_FEED_NAME)
    db.commit()

    assert first is not None and second is not None
    assert first.id == second.id

    teams = db.exec(
        select(Team).where(Team.external_id == str(MARSEILLE_ID))
    ).all()
    assert len(teams) == 1


def test_resolver_records_every_name_as_alias(db: Session) -> None:
    """The merge destroys per-feed spellings unless they are captured here."""
    resolver = EntityResolver(db)
    team = resolver.resolve_team(9147, MATCH_FEED_NAME, authoritative_name=True)
    resolver.resolve_team(9147, EVENT_FEED_NAME)
    db.commit()

    assert team is not None
    aliases = {
        a.name
        for a in db.exec(select(TeamAlias).where(TeamAlias.team_id == team.id)).all()
    }
    assert aliases == {MATCH_FEED_NAME, EVENT_FEED_NAME}


def test_resolver_match_feed_name_wins(db: Session) -> None:
    """§6/H3 tie-break: the match feed's spelling is what the API emits today."""
    resolver = EntityResolver(db)
    resolver.resolve_team(9148, EVENT_FEED_NAME)
    team = resolver.resolve_team(9148, MATCH_FEED_NAME, authoritative_name=True)
    db.commit()

    assert team is not None
    assert team.name == MATCH_FEED_NAME


def test_resolver_event_feed_name_does_not_override(db: Session) -> None:
    resolver = EntityResolver(db)
    resolver.resolve_team(9149, MATCH_FEED_NAME, authoritative_name=True)
    team = resolver.resolve_team(9149, EVENT_FEED_NAME, authoritative_name=False)
    db.commit()

    assert team is not None
    assert team.name == MATCH_FEED_NAME


def test_resolver_fills_gender_and_country_gaps_only(db: Session) -> None:
    """A team first seen via the event feed has neither; the match feed adds them."""
    resolver = EntityResolver(db)
    resolver.resolve_team(9150, EVENT_FEED_NAME)
    team = resolver.resolve_team(
        9150, MATCH_FEED_NAME, authoritative_name=True, gender="male", country_name="France"
    )
    db.commit()

    assert team is not None
    assert team.gender == "male"
    assert team.country_name == "France"


def test_resolver_normalizes_float_ids_to_the_same_team(db: Session) -> None:
    """`3348.0` and `3348` are the same entity, not two."""
    resolver = EntityResolver(db)
    a = resolver.resolve_team("9151.0", "Float FC")
    b = resolver.resolve_team(9151, "Float FC")
    db.commit()

    assert a is not None and b is not None
    assert a.id == b.id


def test_resolver_returns_none_for_missing_id(db: Session) -> None:
    resolver = EntityResolver(db)
    assert resolver.resolve_team(None, "Nobody") is None


# ── IdentityBackfillService ─────────────────────────────────────────────────


def _marseille_fixture(db: Session, *, statsbomb_base: int) -> tuple[uuid.UUID, uuid.UUID]:
    """A match whose feeds disagree about team 147's name, with matching events."""
    comp = create_competition(
        db, statsbomb_id=statsbomb_base, season_id=statsbomb_base
    )
    match = create_match(
        db,
        comp.id,
        statsbomb_id=statsbomb_base,
        home_team=MATCH_FEED_NAME,
        away_team="Guingamp",
        raw={"home_team_id": MARSEILLE_ID, "away_team_id": 142},
    )
    create_event(
        db,
        match.id,
        statsbomb_id=str(uuid.uuid4()),
        team=EVENT_FEED_NAME,
        possession_team_name=EVENT_FEED_NAME,
        raw_event={
            "team_id": MARSEILLE_ID,
            "possession_team_id": MARSEILLE_ID,
            "position": "Right Defensive Midfield",
        },
    )
    lineup = create_lineup(
        db,
        match.id,
        team_name=EVENT_FEED_NAME,
        statsbomb_player_id=statsbomb_base,
        raw={
            "positions": [
                {"position_id": "9", "position": "Right Defensive Midfield"}
            ]
        },
    )
    return match.id, lineup.id


class _ZeroCountSession:
    """A session that reports every count as zero — the post-test-run state."""

    def exec(self, *_args: object, **_kwargs: object) -> "_ZeroCountSession":
        return self

    def one(self) -> int:
        return 0


def test_backfill_refuses_to_run_against_empty_input() -> None:
    """§7.1a: an empty run looks identical to a clean one unless it refuses.

    The test suite deletes all soccer data, so "migration -> tests -> backfill"
    silently destroys the backfill's own input. Without this guard the backfill
    reports zero rows updated and everything downstream reads as green.

    Built with __new__ so the guard can be exercised without a live session,
    and without deleting the fixtures the rest of this session depends on.
    """
    service = IdentityBackfillService.__new__(IdentityBackfillService)
    service.session = _ZeroCountSession()  # type: ignore[assignment]

    with pytest.raises(EmptyBackfillInputError, match="Refusing to backfill"):
        service.assert_inputs_present()


def test_backfill_resolves_marseille_to_one_team(db: Session) -> None:
    """The acceptance test for the whole phase (§3)."""
    _marseille_fixture(db, statsbomb_base=77101)
    IdentityBackfillService(db).run()

    teams = db.exec(
        select(Team).where(Team.external_id == str(MARSEILLE_ID))
    ).all()
    assert len(teams) == 1
    assert teams[0].name == MATCH_FEED_NAME

    aliases = {
        a.name
        for a in db.exec(
            select(TeamAlias).where(TeamAlias.team_id == teams[0].id)
        ).all()
    }
    assert aliases == {MATCH_FEED_NAME, EVENT_FEED_NAME}


def test_backfill_sets_match_team_ids(db: Session) -> None:
    from app.models.match import SoccerMatch

    match_id, _ = _marseille_fixture(db, statsbomb_base=77102)
    IdentityBackfillService(db).run()

    match = db.get(SoccerMatch, match_id)
    assert match is not None
    assert match.home_team_id is not None
    team = db.get(Team, match.home_team_id)
    assert team is not None
    assert team.external_id == str(MARSEILLE_ID)


def test_backfill_lineup_team_resolves_through_event_feed_not_match_teams(
    db: Session,
) -> None:
    """Required negative test for §1.6/B0 — do not delete.

    An earlier revision of the plan resolved `lineup.team_id` by matching
    `lineup.team_name` against the parent match's two team names. That is still
    a name comparison, just scoped to two candidates, and it fails exactly here:
    the lineup says "Marseille", the match says "Olympique de Marseille", and
    the rule produces NULL.

    This fixture is built so the wrong rule cannot pass: the lineup's team name
    appears nowhere in the match row. If someone reintroduces it, team_id comes
    back NULL and this fails.
    """
    match_id, lineup_id = _marseille_fixture(db, statsbomb_base=77103)
    IdentityBackfillService(db).run()

    from app.models.lineup import Lineup
    from app.models.match import SoccerMatch

    lineup = db.get(Lineup, lineup_id)
    match = db.get(SoccerMatch, match_id)
    assert lineup is not None and match is not None

    assert lineup.team_name not in (match.home_team, match.away_team), (
        "fixture no longer exercises B0 — the lineup name now matches the "
        "match feed, so a name-based rule would pass"
    )
    assert lineup.team_id is not None, "lineup.team_id must resolve via the event feed"
    assert lineup.team_id == match.home_team_id


def test_backfill_sets_event_fks(db: Session) -> None:
    from app.models.event import Event

    match_id, _ = _marseille_fixture(db, statsbomb_base=77104)
    IdentityBackfillService(db).run()

    events = db.exec(select(Event).where(Event.match_id == match_id)).all()
    assert events
    for event in events:
        assert event.team_id is not None
        assert event.possession_team_id is not None


def test_backfill_builds_positions_from_lineup_feed(db: Session) -> None:
    """`raw_event` carries no position_id — only `lineup.raw` does."""
    _marseille_fixture(db, statsbomb_base=77105)
    IdentityBackfillService(db).run()

    position = db.exec(
        select(Position).where(Position.name == "Right Defensive Midfield")
    ).first()
    assert position is not None
    assert position.external_id == "9"


def test_backfill_resolves_event_position_by_name(db: Session) -> None:
    from app.models.event import Event

    match_id, _ = _marseille_fixture(db, statsbomb_base=77106)
    IdentityBackfillService(db).run()

    event = db.exec(select(Event).where(Event.match_id == match_id)).first()
    assert event is not None
    assert event.position_id is not None
    position = db.get(Position, event.position_id)
    assert position is not None
    assert position.name == "Right Defensive Midfield"


def test_backfill_is_idempotent(db: Session) -> None:
    _marseille_fixture(db, statsbomb_base=77107)
    IdentityBackfillService(db).run()
    before = len(db.exec(select(Team)).all())

    second = IdentityBackfillService(db).run()
    after = len(db.exec(select(Team)).all())

    assert after == before
    assert second.teams_created == 0


def test_event_filter_by_match_feed_name_finds_event_feed_events(db: Session) -> None:
    """The Marseille bug itself (§1.2), at the point where users hit it.

    `/matches/teams` fills the dropdown from the match feed, so the UI sends
    "Olympique de Marseille". The events were ingested from the event feed and
    say "Marseille". Before this phase the string comparison matched nothing
    and the UI showed an empty pitch for a team with thousands of events.
    """
    from app.repositories.event import EventRepository

    match_id, _ = _marseille_fixture(db, statsbomb_base=77109)
    IdentityBackfillService(db).run()

    events, count = EventRepository(db).list_by_match(match_id, team=MATCH_FEED_NAME)
    assert count == 1, "match-feed spelling must find event-feed events"
    assert events[0].team == EVENT_FEED_NAME


def test_event_filter_still_works_for_the_event_feed_name(db: Session) -> None:
    from app.repositories.event import EventRepository

    match_id, _ = _marseille_fixture(db, statsbomb_base=77110)
    IdentityBackfillService(db).run()

    _, count = EventRepository(db).list_by_match(match_id, team=EVENT_FEED_NAME)
    assert count == 1


def test_event_filter_falls_back_to_name_when_team_id_is_null(db: Session) -> None:
    """Events ingested before the backfill must not vanish from filtered results.

    This is why the filter ORs the id and name clauses instead of swapping one
    for the other — a straight swap would silently hide every un-backfilled row.
    """
    from app.repositories.event import EventRepository

    comp = create_competition(db, statsbomb_id=77111, season_id=77111)
    match = create_match(db, comp.id, statsbomb_id=77111, home_team="Solo FC")
    create_event(db, match.id, statsbomb_id=str(uuid.uuid4()), team="Solo FC")

    _, count = EventRepository(db).list_by_match(match.id, team="Solo FC")
    assert count == 1


def test_event_filter_by_team_id_is_exact(db: Session) -> None:
    from app.models.match import SoccerMatch
    from app.repositories.event import EventRepository

    match_id, _ = _marseille_fixture(db, statsbomb_base=77112)
    IdentityBackfillService(db).run()

    match = db.get(SoccerMatch, match_id)
    assert match is not None and match.home_team_id is not None
    _, count = EventRepository(db).list_by_match(
        match_id, team_id=match.home_team_id
    )
    assert count == 1


def test_match_filter_by_team_id(db: Session) -> None:
    from app.models.match import SoccerMatch
    from app.repositories.match import MatchRepository

    match_id, _ = _marseille_fixture(db, statsbomb_base=77113)
    IdentityBackfillService(db).run()

    match = db.get(SoccerMatch, match_id)
    assert match is not None and match.home_team_id is not None
    rows, count, _ = MatchRepository(db).list_all(team_id=match.home_team_id)
    assert match_id in {r.id for r in rows}
    assert count >= 1


def test_backfill_stamps_player_source_columns(db: Session) -> None:
    player = Player(statsbomb_id=771080, name="Backfill Test Player")
    db.add(player)
    db.commit()

    _marseille_fixture(db, statsbomb_base=77108)
    IdentityBackfillService(db).run()

    db.refresh(player)
    assert player.source_id is not None
    assert player.external_id == "771080"
