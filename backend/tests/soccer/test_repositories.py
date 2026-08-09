import random
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import event, inspect
from sqlmodel import Session

from app.exceptions.competition import CompetitionNotFoundError
from app.models.player import Player
from app.repositories.competition import CompetitionRepository
from app.repositories.event import EventRepository
from app.repositories.frame360 import Frame360Repository
from app.repositories.lineup import LineupRepository
from app.repositories.match import MatchRepository
from app.repositories.player import PlayerRepository
from tests.utils.soccer import (
    create_competition,
    create_event,
    create_frame,
    create_lineup,
    create_match,
)

# ── CompetitionRepository ──────────────────────────────────────────────────


def test_competition_list_all_empty(db: Session) -> None:
    repo = CompetitionRepository(db)
    rows, count = repo.list_all()
    assert isinstance(rows, list)
    assert count >= 0


def test_competition_list_all_returns_seeded(db: Session) -> None:
    create_competition(db, statsbomb_id=1001, season_id=1001)
    repo = CompetitionRepository(db)
    rows, count = repo.list_all()
    assert count >= 1
    assert any(c.statsbomb_id == 1001 for c, _ in rows)


def test_competition_get_existing_keys(db: Session) -> None:
    create_competition(db, statsbomb_id=1002, season_id=1002)
    repo = CompetitionRepository(db)
    keys = repo.get_existing_keys()
    assert (1002, 1002) in keys


def test_competition_get_by_statsbomb_key(db: Session) -> None:
    create_competition(db, statsbomb_id=1003, season_id=1003)
    repo = CompetitionRepository(db)
    comp = repo.get_by_statsbomb_key(1003, 1003)
    assert comp.statsbomb_id == 1003


def test_competition_get_by_statsbomb_key_not_found(db: Session) -> None:
    repo = CompetitionRepository(db)
    with pytest.raises(CompetitionNotFoundError):
        repo.get_by_statsbomb_key(99999, 99999)


def test_competition_list_all_has_events_filter(db: Session) -> None:
    comp_with_events = create_competition(db, statsbomb_id=1004, season_id=1004)
    comp_matches_only = create_competition(db, statsbomb_id=1005, season_id=1005)
    match_with_events = create_match(db, comp_with_events.id, statsbomb_id=10041)
    create_match(db, comp_matches_only.id, statsbomb_id=10051)
    create_event(db, match_with_events.id)

    repo = CompetitionRepository(db)
    rows, count = repo.list_all(has_events=True)
    ids = [c.id for c, _ in rows]
    assert comp_with_events.id in ids
    assert comp_matches_only.id not in ids
    assert count == len(rows)


def test_competition_list_all_has_events_false_includes_matches_only(
    db: Session,
) -> None:
    comp = create_competition(db, statsbomb_id=1006, season_id=1006)
    create_match(db, comp.id, statsbomb_id=10061)

    repo = CompetitionRepository(db)
    rows, _ = repo.list_all(has_matches=True, has_events=False)
    assert any(c.id == comp.id for c, _ in rows)


@contextmanager
def capture_sql(session: Session) -> Iterator[list[str]]:
    """Record every statement the session's engine executes inside the block."""
    statements: list[str] = []
    engine = session.get_bind()

    def record(_conn: object, _cursor: object, statement: str, *_rest: object) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_competition_list_all_returns_session_attached_rows(db: Session) -> None:
    """list_all must hand back the live ORM row, not a detached copy.

    `Model.model_validate(row)` on a `table=True` class builds a *new transient*
    instance. It is never attached to the session, so it silently drops out of
    the identity map: refreshing it, mutating it, or re-querying it no longer
    refers to the same row.
    """
    comp = create_competition(db, statsbomb_id=1007, season_id=1007)
    create_match(db, comp.id, statsbomb_id=10071)

    rows, _ = CompetitionRepository(db).list_all()
    returned = next(c for c, _ in rows if c.id == comp.id)

    assert inspect(returned).persistent, "row is detached from the session"
    assert returned is comp, "row is a copy, not the identity-mapped instance"


def test_competition_list_all_does_not_lazy_load_matches(db: Session) -> None:
    """`model_validate` resolves `Competition.matches` — one extra query per row.

    Contrary to what one might expect, the relationship is not dropped by the
    copy: it is *eagerly walked* while building it. So the cost is a hidden N+1
    plus every SoccerMatch hydrated into memory, for a column no caller reads.
    """
    comp = create_competition(db, statsbomb_id=1008, season_id=1008)
    for i in range(3):
        create_match(db, comp.id, statsbomb_id=10080 + i)

    with capture_sql(db) as statements:
        CompetitionRepository(db).list_all()

    lazy_loads = [s for s in statements if "FROM soccer_match" in s]
    assert lazy_loads == [], f"{len(lazy_loads)} per-row soccer_match queries"


def test_player_list_all_returns_session_attached_rows(db: Session) -> None:
    """Same detached-copy defect on the player path."""
    statsbomb_id = random.randint(10_000_000, 99_999_999)
    player = Player(statsbomb_id=statsbomb_id, name="Relationship Probe")
    db.add(player)
    db.commit()
    try:
        rows, _ = PlayerRepository(db).list_all(name_search="Relationship Probe")
        returned = next(p for p, _ in rows if p.id == player.id)

        assert inspect(returned).persistent, "row is detached from the session"
        assert returned is player, "row is a copy, not the identity-mapped instance"
    finally:
        # conftest's _wipe_soccer_data does not cover `player`.
        db.delete(player)
        db.commit()


# ── MatchRepository ────────────────────────────────────────────────────────


def test_match_list_all(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=2001, season_id=2001)
    create_match(db, comp.id, statsbomb_id=20001)
    repo = MatchRepository(db)
    rows, count, _ = repo.list_all()
    assert count >= 1
    assert any(m.statsbomb_id == 20001 for m in rows)


def test_match_list_all_filter_by_competition(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=2002, season_id=2002)
    create_match(db, comp.id, statsbomb_id=20002)
    repo = MatchRepository(db)
    rows, count, _ = repo.list_all(competition_season_id=comp.id)
    assert count >= 1
    assert all(m.competition_season_id == comp.id for m in rows)


def test_match_list_all_has_events_filter(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=2003, season_id=2003)
    match_with = create_match(db, comp.id, statsbomb_id=20003)
    match_without = create_match(db, comp.id, statsbomb_id=20004)
    create_event(db, match_with.id)

    repo = MatchRepository(db)
    rows, count, _ = repo.list_all(has_events=True)
    ids = [m.id for m in rows]
    assert match_with.id in ids
    assert match_without.id not in ids


def test_match_get_existing_statsbomb_ids(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=2004, season_id=2004)
    create_match(db, comp.id, statsbomb_id=20005)
    repo = MatchRepository(db)
    ids = repo.get_existing_statsbomb_ids()
    assert 20005 in ids


def test_match_list_for_competition(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=2005, season_id=2005)
    create_match(db, comp.id, statsbomb_id=20006)
    repo = MatchRepository(db)
    matches = repo.list_for_competition(2005, 2005)
    assert any(m.statsbomb_id == 20006 for m in matches)


def test_match_list_for_competition_missing_comp(db: Session) -> None:
    repo = MatchRepository(db)
    matches = repo.list_for_competition(99999, 99999)
    assert matches == []


def test_match_list_distinct_teams(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=2006, season_id=2006)
    create_match(
        db, comp.id, statsbomb_id=20007, home_team="Gamma United", away_team="Delta FC"
    )
    create_match(
        db, comp.id, statsbomb_id=20008, home_team="Delta FC", away_team="Epsilon City"
    )
    repo = MatchRepository(db)
    teams = repo.list_distinct_teams(competition_season_id=comp.id)
    assert teams == ["Delta FC", "Epsilon City", "Gamma United"]


def test_match_list_distinct_teams_filter_by_competition(db: Session) -> None:
    comp_a = create_competition(db, statsbomb_id=2007, season_id=2007)
    comp_b = create_competition(db, statsbomb_id=2008, season_id=2008)
    create_match(
        db, comp_a.id, statsbomb_id=20009, home_team="Zeta A", away_team="Eta A"
    )
    create_match(
        db, comp_b.id, statsbomb_id=20010, home_team="Theta B", away_team="Iota B"
    )
    repo = MatchRepository(db)
    teams = repo.list_distinct_teams(competition_season_id=comp_a.id)
    assert "Zeta A" in teams
    assert "Eta A" in teams
    assert "Theta B" not in teams


def test_match_list_distinct_teams_has_events_filter(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=2009, season_id=2009)
    match_with = create_match(
        db, comp.id, statsbomb_id=20011, home_team="Kappa FC", away_team="Lambda FC"
    )
    create_match(db, comp.id, statsbomb_id=20012, home_team="Mu FC", away_team="Nu FC")
    create_event(db, match_with.id)

    repo = MatchRepository(db)
    teams = repo.list_distinct_teams(competition_season_id=comp.id, has_events=True)
    assert teams == ["Kappa FC", "Lambda FC"]


# ── EventRepository ────────────────────────────────────────────────────────


def test_event_list_by_match(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=3001, season_id=3001)
    match = create_match(db, comp.id, statsbomb_id=30001)
    ev = create_event(db, match.id)

    repo = EventRepository(db)
    events, count = repo.list_by_match(match.id)
    assert count == 1
    assert events[0].id == ev.id


def test_event_list_by_match_empty(db: Session) -> None:
    repo = EventRepository(db)
    events, count = repo.list_by_match(uuid.uuid4())
    assert count == 0
    assert events == []


def test_event_get_existing_statsbomb_ids(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=3002, season_id=3002)
    match = create_match(db, comp.id, statsbomb_id=30002)
    ev = create_event(db, match.id, statsbomb_id="test-ev-id-001")

    repo = EventRepository(db)
    ids = repo.get_existing_statsbomb_ids()
    assert ev.statsbomb_id in ids


def test_event_list_by_match_filter_by_player(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=3003, season_id=3003)
    match = create_match(db, comp.id, statsbomb_id=30003)
    ev = create_event(db, match.id, player="Alice")
    create_event(db, match.id, player="Bob")

    repo = EventRepository(db)
    events, count = repo.list_by_match(match.id, player="Alice")
    assert count == 1
    assert events[0].id == ev.id


def test_event_list_by_match_filter_by_possession(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=3004, season_id=3004)
    match = create_match(db, comp.id, statsbomb_id=30004)
    ev = create_event(db, match.id, possession=1)
    create_event(db, match.id, possession=2)

    repo = EventRepository(db)
    events, count = repo.list_by_match(match.id, possession=1)
    assert count == 1
    assert events[0].id == ev.id


# ── LineupRepository ───────────────────────────────────────────────────────


def test_lineup_has_lineups_for_match(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=4001, season_id=4001)
    match = create_match(db, comp.id, statsbomb_id=40001)
    repo = LineupRepository(db)
    assert not repo.has_lineups_for_match(match.id)
    create_lineup(db, match.id)
    assert repo.has_lineups_for_match(match.id)


def test_lineup_list_by_match(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=4002, season_id=4002)
    match = create_match(db, comp.id, statsbomb_id=40002)
    create_lineup(
        db, match.id, player_name="Alice", jersey_number=1, statsbomb_player_id=4101
    )
    create_lineup(
        db, match.id, player_name="Bob", jersey_number=2, statsbomb_player_id=4102
    )

    repo = LineupRepository(db)
    players, count = repo.list_by_match(match.id)
    assert count == 2
    assert {p.player_name for p in players} == {"Alice", "Bob"}


# ── Frame360Repository ─────────────────────────────────────────────────────


def test_frame360_list_by_match(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=5001, season_id=5001)
    match = create_match(db, comp.id, statsbomb_id=50001)
    frame = create_frame(db, match.id, "evt-frame-001")

    repo = Frame360Repository(db)
    frames, count = repo.list_by_match(match.id)
    assert count == 1
    assert frames[0].id == frame.id


def test_frame360_get_existing_event_ids(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=5002, season_id=5002)
    match = create_match(db, comp.id, statsbomb_id=50002)
    create_frame(db, match.id, "evt-frame-002")

    repo = Frame360Repository(db)
    ids = repo.get_existing_event_ids_for_match(match.id)
    assert "evt-frame-002" in ids
