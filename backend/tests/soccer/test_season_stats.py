"""Minutes played and per-90 season stats for a single player."""

import uuid

import pytest
from sqlmodel import Session, col, select

from app.models.competition import Competition, CompetitionSeason, Season
from app.models.lineup_position import LineupPosition
from app.models.player import Player
from app.services.lineup_position_backfill import (
    LineupPositionBackfillService,
    parse_clock,
)
from app.services.player import PlayerService
from tests.utils.soccer import (
    create_competition,
    create_event,
    create_lineup,
    create_match,
)

# The match's last event, so an open-ended stint has a real final whistle to
# resolve against — 92:30, deliberately not a round 90.
FINAL_MINUTE = 92
FINAL_SECOND = 30
MATCH_END_SECONDS = FINAL_MINUTE * 60 + FINAL_SECOND


# ── parse_clock ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("00:00", 0),
        ("44:12", 2652),
        # Past 60 minutes: this is elapsed match time, not a wall clock, so
        # "69:35" must not roll over into an hour.
        ("69:35", 4175),
        ("90:00", 5400),
        (None, None),
    ],
)
def test_parse_clock(raw: str | None, expected: int | None) -> None:
    assert parse_clock(raw) == expected


def test_parse_clock_rejects_unrecognised_format() -> None:
    with pytest.raises(ValueError, match="unrecognised match clock"):
        parse_clock("01:02:03")


# ── fixture ─────────────────────────────────────────────────────────────────


def _season_fixture(
    db: Session,
    *,
    base: int,
    stints: list[dict],
    pass_events: int,
) -> tuple[uuid.UUID, uuid.UUID]:
    """One player, one match, a known number of passes. Returns (player, season)."""
    # Created explicitly: the player table is normally populated by the lineup
    # ingest, which these fixtures bypass by inserting lineups directly.
    player_name = f"Stat Player {base}"
    db.add(Player(statsbomb_id=base, name=player_name))
    db.commit()
    comp = create_competition(db, statsbomb_id=base, season_id=base)
    match = create_match(
        db,
        comp.id,
        statsbomb_id=base,
        home_team="Stat FC",
        away_team="Rival FC",
        raw={"home_team_id": base, "away_team_id": base + 1},
    )
    for index in range(pass_events):
        create_event(
            db,
            match.id,
            statsbomb_id=str(uuid.uuid4()),
            index=index + 1,
            type_name="Pass",
            team="Stat FC",
            player=player_name,
            raw_event={
                "team_id": base,
                "player_id": base,
                "position": "Center Forward",
            },
        )
    # The final whistle an open-ended stint resolves to.
    create_event(
        db,
        match.id,
        statsbomb_id=str(uuid.uuid4()),
        index=pass_events + 1,
        type_name="Half End",
        team="Stat FC",
        minute=FINAL_MINUTE,
        second=FINAL_SECOND,
        raw_event={"team_id": base},
    )
    create_lineup(
        db,
        match.id,
        team_name="Stat FC",
        statsbomb_player_id=base,
        player_name=player_name,
        raw={"positions": stints},
    )
    db.commit()

    # The fixtures resolve team/player/competition/season as they build, so
    # only the stint flattening still needs a backfill pass.
    LineupPositionBackfillService(db).run()

    player = db.exec(select(Player).where(Player.statsbomb_id == base)).one()
    edition = db.exec(
        select(CompetitionSeason)
        .join(Competition, col(CompetitionSeason.competition_id) == Competition.id)
        .where(Competition.external_id == str(base))
    ).one()
    assert edition.season_id is not None
    return player.id, edition.season_id


_FULL_MATCH_STINT = [
    {
        "from": "00:00",
        "to": None,
        "from_period": 1,
        "to_period": 2,
        "position_id": 23,
        "position": "Center Forward",
        "start_reason": "Starting XI",
        "end_reason": "Final Whistle",
    }
]


# ── backfill ────────────────────────────────────────────────────────────────


def test_open_ended_stint_resolves_to_the_final_whistle(db: Session) -> None:
    """The heart of the per-90 gate.

    Over half the stints in the real data (8,339 of 15,276) have no end time —
    the player was still on at the whistle. Assuming a flat 90 minutes makes
    every per-90 quietly wrong by the stoppage-time fraction; assuming 0 makes
    substitutes' rates explode. The correct end is the match's last event.
    """
    player_id, _ = _season_fixture(
        db, base=93001, stints=_FULL_MATCH_STINT, pass_events=3
    )

    lineup_positions = db.exec(
        select(LineupPosition).where(LineupPosition.from_seconds == 0)
    ).all()
    stint = next(lp for lp in lineup_positions if lp.end_reason == "Final Whistle")
    assert stint.to_seconds == MATCH_END_SECONDS, (
        "must resolve to the match's own final event, not a hardcoded 90:00"
    )


def test_multi_stint_minutes_sum(db: Session) -> None:
    """A player who shifts position mid-match has several stints; minutes add up."""
    stints = [
        {
            "from": "00:00",
            "to": "30:00",
            "from_period": 1,
            "to_period": 1,
            "position_id": 23,
            "position": "Center Forward",
            "start_reason": "Starting XI",
            "end_reason": "Tactical Shift",
        },
        {
            "from": "30:00",
            "to": "60:00",
            "from_period": 1,
            "to_period": 2,
            "position_id": 23,
            "position": "Center Forward",
            "start_reason": "Tactical Shift",
            "end_reason": "Substitution - Off (Tactical)",
        },
    ]
    player_id, season_id = _season_fixture(db, base=93002, stints=stints, pass_events=2)

    stats = PlayerService(db).get_season_stats(player_id, season_id)
    assert stats is not None
    assert stats.minutes_played == 60.0
    assert stats.appearances == 1


def test_backfill_is_idempotent(db: Session) -> None:
    _season_fixture(db, base=93003, stints=_FULL_MATCH_STINT, pass_events=1)
    before = len(db.exec(select(LineupPosition)).all())

    second = LineupPositionBackfillService(db).run()
    assert second.stints_created == 0
    assert len(db.exec(select(LineupPosition)).all()) == before


# ── per-90 ──────────────────────────────────────────────────────────────────


def test_per_90_matches_a_hand_computed_value(db: Session) -> None:
    """Per-90 must match a value computed by hand.

    Raw counts would pass under a broken minutes calculation — only a rate
    catches it. The arithmetic is deliberately written out rather than
    re-derived from the service, so a bug there cannot move the expectation
    with it.
    """
    player_id, season_id = _season_fixture(
        db, base=93004, stints=_FULL_MATCH_STINT, pass_events=10
    )

    stats = PlayerService(db).get_season_stats(player_id, season_id)
    assert stats is not None

    # Played 00:00 to the final whistle at 92:30 => 5550 seconds => 92.5 minutes.
    assert stats.minutes_played == 92.5

    # 10 passes over 92.5 minutes => 10 * 90 / 92.5 = 9.729... => 9.73
    expected_per_90 = round(10 * 90.0 / 92.5, 2)
    assert expected_per_90 == 9.73

    passes = next(line for line in stats.stats if line.type_name == "Pass")
    assert passes.count == 10
    assert passes.per_90 == expected_per_90


def test_per_90_is_not_inflated_by_assuming_90_minutes(db: Session) -> None:
    """Guards the specific wrong answer a flat-90 assumption would produce."""
    player_id, season_id = _season_fixture(
        db, base=93005, stints=_FULL_MATCH_STINT, pass_events=10
    )
    stats = PlayerService(db).get_season_stats(player_id, season_id)
    assert stats is not None

    passes = next(line for line in stats.stats if line.type_name == "Pass")
    naive = round(10 * 90.0 / 90.0, 2)  # 10.0 — what a hardcoded 90 would give
    assert passes.per_90 != naive
    assert passes.per_90 == 9.73


def test_season_filter_scopes_the_stats(db: Session) -> None:
    player_id, season_id = _season_fixture(
        db, base=93006, stints=_FULL_MATCH_STINT, pass_events=4
    )
    other_season = db.exec(select(Season).where(Season.id != season_id)).first()
    assert other_season is not None

    scoped = PlayerService(db).get_season_stats(player_id, other_season.id)
    assert scoped is not None
    assert scoped.appearances == 0
    assert scoped.minutes_played == 0.0
    assert scoped.stats == []


def test_per_90_is_zero_rather_than_dividing_by_zero(db: Session) -> None:
    player = Player(statsbomb_id=93007, name="Never Played")
    db.add(player)
    db.commit()

    stats = PlayerService(db).get_season_stats(player.id)
    assert stats is not None
    assert stats.minutes_played == 0.0
    assert stats.appearances == 0


def test_unknown_player_returns_none(db: Session) -> None:
    assert PlayerService(db).get_season_stats(uuid.uuid4()) is None


def test_unused_substitute_is_not_an_appearance(db: Session) -> None:
    """A named substitute who never came on has no stint, so no appearance."""
    player_id, season_id = _season_fixture(db, base=93008, stints=[], pass_events=1)
    stats = PlayerService(db).get_season_stats(player_id, season_id)
    assert stats is not None
    assert stats.appearances == 0
    assert stats.minutes_played == 0.0


def test_overlapping_stints_do_not_double_count(db: Session) -> None:
    """Minutes are the union of on-pitch intervals, not the sum of stints.

    StatsBomb's lineup feed emits overlapping stints on some knockout matches,
    where the clock appears to restart mid-game. Messi's 2022 final reads
    00:00->115:32, then 115:32->28:11 (backward), then 28:19->Final Whistle.
    Summed that is 213 minutes of a 126-minute match; merged it is the full
    match, which is correct.

    The fixture reproduces the shape: a stint covering the whole match, then a
    second one wholly inside it. Summing gives 150; the union gives 92.5.
    """
    stints = [
        {
            "from": "00:00",
            "to": None,
            "from_period": 1,
            "to_period": 2,
            "position_id": 23,
            "position": "Center Forward",
            "start_reason": "Starting XI",
            "end_reason": "Final Whistle",
        },
        {
            # Entirely contained in the stint above — contributes no new time.
            "from": "10:00",
            "to": "70:00",
            "from_period": 1,
            "to_period": 2,
            "position_id": 23,
            "position": "Center Forward",
            "start_reason": "Tactical Shift",
            "end_reason": "Tactical Shift",
        },
    ]
    player_id, season_id = _season_fixture(db, base=93009, stints=stints, pass_events=2)

    stats = PlayerService(db).get_season_stats(player_id, season_id)
    assert stats is not None
    # 92:30 final whistle, not 92.5 + 60 = 152.5.
    assert stats.minutes_played == 92.5
    assert stats.appearances == 1


def test_minutes_never_exceed_the_match_length(db: Session) -> None:
    """The invariant the overlap bug violated: you cannot play longer than the match."""
    stints = [
        {
            "from": "00:00",
            "to": "80:00",
            "from_period": 1,
            "to_period": 2,
            "position_id": 23,
            "position": "Center Forward",
            "start_reason": "Starting XI",
            "end_reason": "Tactical Shift",
        },
        {
            # Backward clock, as the real feed produces.
            "from": "80:00",
            "to": "20:00",
            "from_period": 2,
            "to_period": 1,
            "position_id": 23,
            "position": "Center Forward",
            "start_reason": "Tactical Shift",
            "end_reason": "Player Off",
        },
        {
            "from": "20:10",
            "to": None,
            "from_period": 1,
            "to_period": 2,
            "position_id": 23,
            "position": "Center Forward",
            "start_reason": "Player On",
            "end_reason": "Final Whistle",
        },
    ]
    player_id, season_id = _season_fixture(db, base=93010, stints=stints, pass_events=1)

    stats = PlayerService(db).get_season_stats(player_id, season_id)
    assert stats is not None
    assert stats.minutes_played <= MATCH_END_SECONDS / 60.0
