from unittest.mock import patch

import pandas as pd
import pytest
from sqlmodel import Session, select

from app.exceptions.event import StatsBombFetchError
from app.models.event import Event
from app.models.match import SoccerMatch
from app.services.competition import CompetitionService
from app.services.event import EventService
from app.services.frame360 import Frame360Service
from app.services.lineup import LineupService
from app.services.match import MatchService
from tests.utils.soccer import create_competition, create_match


def _competitions_df(competition_id: int, season_id: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "competition_id": competition_id,
                "season_id": season_id,
                "country_name": "Test Country",
                "competition_name": "Test League",
                "competition_gender": "male",
                "competition_youth": False,
                "competition_international": False,
                "season_name": "2099",
                "match_updated": None,
                "match_available": None,
                "match_updated_360": None,
                "match_available_360": None,
            }
        ]
    )


def _matches_df(match_id: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "match_id": match_id,
                "match_date": "2099-06-01",
                "kick_off": "15:00:00.000",
                "home_team": "Team A",
                "away_team": "Team B",
                "home_score": 2,
                "away_score": 1,
                "stadium": None,
                "referee": None,
                "match_week": 1,
                "competition_stage": "Group Stage",
                "home_team_gender": None,
                "away_team_gender": None,
                "home_team_country_name": None,
                "away_team_country_name": None,
                "home_team_group": None,
                "away_team_group": None,
                "home_manager_name": None,
                "away_manager_name": None,
                "match_status": "available",
                "last_updated": None,
                "match_status_360": None,
            }
        ]
    )


def _events_df(event_id: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": event_id,
                "index": 1,
                "period": 1,
                "timestamp": "00:00:00.000",
                "minute": 0,
                "second": 0,
                "type": {"name": "Kick Off"},
                "possession": 1,
                "possession_team": {"name": "Team A"},
                "play_pattern": {"name": "Regular Play"},
                "team": {"name": "Team A"},
                "player": None,
                "location": [60.0, 40.0],
                "duration": 0.0,
                "under_pressure": None,
                "off_camera": None,
                "out": None,
            }
        ]
    )


def _lineups_dict() -> dict:
    return {
        "Team A": pd.DataFrame(
            [
                {
                    "player_id": 9001,
                    "player_name": "Alice",
                    "player_nickname": None,
                    "jersey_number": 10,
                    "country": {"name": "France"},
                    "cards": [],
                    "positions": [
                        {
                            "position_id": 1,
                            "position": "Goalkeeper",
                            "from": "00:00",
                            "to": None,
                            "from_period": 1,
                            "to_period": None,
                            "start_reason": "Starting XI",
                            "end_reason": "Final Whistle",
                        }
                    ],
                }
            ]
        )
    }


def _frames_df(event_id: str) -> pd.DataFrame:
    return pd.DataFrame(
        [{"id": event_id, "visible_area": [0, 80, 120, 80], "freeze_frame": []}]
    )


# ── CompetitionService ─────────────────────────────────────────────────────

# IDs 6001-6002 reserved for competition service tests


def test_competition_service_ingest_new(db: Session) -> None:
    with patch(
        "statsbombpy.sb.competitions", return_value=_competitions_df(6001, 6001)
    ):
        n, comps = CompetitionService(db).ingest()
    assert n >= 1
    assert any(c.statsbomb_id == 6001 for c in comps)


def test_competition_service_ingest_idempotent(db: Session) -> None:
    comps_df = _competitions_df(6002, 6002)
    with patch("statsbombpy.sb.competitions", return_value=comps_df):
        n1, _ = CompetitionService(db).ingest()
    with patch("statsbombpy.sb.competitions", return_value=comps_df):
        n2, _ = CompetitionService(db).ingest()
    assert n1 >= 1
    assert n2 == 0


# ── MatchService ───────────────────────────────────────────────────────────

# IDs 6003-6005 reserved for match service tests


def test_match_service_ingest(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6003, season_id=6003)
    with patch("statsbombpy.sb.matches", return_value=_matches_df(60001)):
        n = MatchService(db).ingest([comp])
    assert n >= 1


def test_match_service_ingest_skips_fetch_error(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6004, season_id=6004)
    with patch("statsbombpy.sb.matches", side_effect=Exception("network error")):
        n = MatchService(db).ingest([comp])
    assert n == 0


def test_match_service_ingest_idempotent(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6005, season_id=6005)
    with patch("statsbombpy.sb.matches", return_value=_matches_df(60002)):
        n1 = MatchService(db).ingest([comp])
    with patch("statsbombpy.sb.matches", return_value=_matches_df(60002)):
        n2 = MatchService(db).ingest([comp])
    assert n1 >= 1
    assert n2 == 0


# IDs 6019-6021 / matches 60016-60018 reserved for raw backfill tests


def _matches_df_with_ids(match_id: int) -> pd.DataFrame:
    """A match row carrying the *_id columns the typed fields drop.

    StatsBombMatchRow declares none of these; they survive only because
    _StatsBombRow sets extra="allow". Phase 1 resolves team FKs from them.
    """
    df = _matches_df(match_id)
    df["home_team_id"] = 147
    df["away_team_id"] = 200
    df["competition_stage_id"] = 10
    return df


def _strip_raw(db: Session, statsbomb_id: int) -> SoccerMatch:
    """Return a match to its pre-`raw`-column state."""
    match = db.exec(
        select(SoccerMatch).where(SoccerMatch.statsbomb_id == statsbomb_id)
    ).one()
    match.raw = None
    db.add(match)
    db.commit()
    return match


def test_match_service_backfill_raw_populates_existing_rows(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6019, season_id=6019)
    with patch("statsbombpy.sb.matches", return_value=_matches_df_with_ids(60016)):
        MatchService(db).ingest([comp])
    db.commit()
    match = _strip_raw(db, 60016)
    assert match.raw is None

    with patch("statsbombpy.sb.matches", return_value=_matches_df_with_ids(60016)):
        updated = MatchService(db).backfill_raw([comp])

    assert updated == 1
    db.refresh(match)
    # The point of the backfill: ids the typed columns never stored.
    assert match.raw is not None
    assert match.raw["home_team_id"] == 147
    assert match.raw["away_team_id"] == 200
    assert match.raw["competition_stage_id"] == 10


def test_match_service_backfill_raw_is_idempotent(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6020, season_id=6020)
    with patch("statsbombpy.sb.matches", return_value=_matches_df_with_ids(60017)):
        MatchService(db).ingest([comp])
    db.commit()
    _strip_raw(db, 60017)

    with patch("statsbombpy.sb.matches", return_value=_matches_df_with_ids(60017)):
        first = MatchService(db).backfill_raw([comp])
    # A second pass must not even re-fetch, so a partial run is safe to repeat.
    with patch("statsbombpy.sb.matches", side_effect=AssertionError("re-fetched")):
        second = MatchService(db).backfill_raw([comp])

    assert first == 1
    assert second == 0


def test_match_service_backfill_raw_survives_fetch_error(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6021, season_id=6021)
    with patch("statsbombpy.sb.matches", return_value=_matches_df_with_ids(60018)):
        MatchService(db).ingest([comp])
    db.commit()
    _strip_raw(db, 60018)

    with patch("statsbombpy.sb.matches", side_effect=Exception("network error")):
        updated = MatchService(db).backfill_raw([comp])

    assert updated == 0


# ── EventService ───────────────────────────────────────────────────────────

# IDs 6006-6008 / matches 60003-60005 reserved for event service tests


def test_event_service_ingest(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6006, season_id=6006)
    create_match(db, comp.id, statsbomb_id=60003)
    with patch("statsbombpy.sb.events", return_value=_events_df("evt-svc-6006-001")):
        n = EventService(db).ingest_for_competition(6006, 6006)
    assert n == 1


def test_event_service_ingest_raises_on_fetch_error(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6007, season_id=6007)
    create_match(db, comp.id, statsbomb_id=60004)
    with patch("statsbombpy.sb.events", side_effect=Exception("fetch failed")):
        with pytest.raises(StatsBombFetchError):
            EventService(db).ingest_for_competition(6007, 6007)


def test_event_service_ingest_idempotent(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6008, season_id=6008)
    create_match(db, comp.id, statsbomb_id=60005)
    with patch("statsbombpy.sb.events", return_value=_events_df("evt-svc-6008-001")):
        n1 = EventService(db).ingest_for_competition(6008, 6008)
    with patch("statsbombpy.sb.events", return_value=_events_df("evt-svc-6008-001")):
        n2 = EventService(db).ingest_for_competition(6008, 6008)
    assert n1 == 1
    assert n2 == 0


# IDs 6014-6018 / matches 60011-60015 reserved for end_location/pass_recipient backfill tests


def _get_event(db: Session, statsbomb_id: str) -> Event:
    return db.exec(select(Event).where(Event.statsbomb_id == statsbomb_id)).one()


def test_event_service_ingest_populates_end_location_from_pass(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6014, season_id=6014)
    create_match(db, comp.id, statsbomb_id=60011)
    events_df = _events_df("evt-svc-6014-001")
    events_df.at[0, "type"] = {"name": "Pass"}
    events_df["pass_end_location"] = [[49.4, 40.6]]
    with patch("statsbombpy.sb.events", return_value=events_df):
        EventService(db).ingest_for_competition(6014, 6014)

    ev = _get_event(db, "evt-svc-6014-001")
    assert ev.end_location_x == 49.4
    assert ev.end_location_y == 40.6


def test_event_service_ingest_populates_end_location_from_shot(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6015, season_id=6015)
    create_match(db, comp.id, statsbomb_id=60012)
    events_df = _events_df("evt-svc-6015-001")
    events_df.at[0, "type"] = {"name": "Shot"}
    events_df["shot_end_location"] = [[120.0, 33.5, 0.4]]
    with patch("statsbombpy.sb.events", return_value=events_df):
        EventService(db).ingest_for_competition(6015, 6015)

    ev = _get_event(db, "evt-svc-6015-001")
    assert ev.end_location_x == 120.0
    assert ev.end_location_y == 33.5


def test_event_service_ingest_no_end_location_for_other_types(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6016, season_id=6016)
    create_match(db, comp.id, statsbomb_id=60013)
    events_df = _events_df("evt-svc-6016-001")
    with patch("statsbombpy.sb.events", return_value=events_df):
        EventService(db).ingest_for_competition(6016, 6016)

    ev = _get_event(db, "evt-svc-6016-001")
    assert ev.end_location_x is None
    assert ev.end_location_y is None


def test_event_service_ingest_populates_pass_recipient(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6017, season_id=6017)
    create_match(db, comp.id, statsbomb_id=60014)
    events_df = _events_df("evt-svc-6017-001")
    events_df.at[0, "type"] = {"name": "Pass"}
    events_df["pass_recipient"] = ["Alice"]
    with patch("statsbombpy.sb.events", return_value=events_df):
        EventService(db).ingest_for_competition(6017, 6017)

    ev = _get_event(db, "evt-svc-6017-001")
    assert ev.pass_recipient == "Alice"


def test_event_service_ingest_no_pass_recipient_for_other_types(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6018, season_id=6018)
    create_match(db, comp.id, statsbomb_id=60015)
    events_df = _events_df("evt-svc-6018-001")
    with patch("statsbombpy.sb.events", return_value=events_df):
        EventService(db).ingest_for_competition(6018, 6018)

    ev = _get_event(db, "evt-svc-6018-001")
    assert ev.pass_recipient is None


# ── LineupService ──────────────────────────────────────────────────────────

# IDs 6009-6011 / matches 60006-60008 reserved for lineup service tests


def test_lineup_service_ingest(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6009, season_id=6009)
    create_match(db, comp.id, statsbomb_id=60006)
    with patch("statsbombpy.sb.lineups", return_value=_lineups_dict()):
        n = LineupService(db).ingest_for_competition(6009, 6009)
    assert n == 1


def test_lineup_service_ingest_idempotent(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6010, season_id=6010)
    create_match(db, comp.id, statsbomb_id=60007)
    with patch("statsbombpy.sb.lineups", return_value=_lineups_dict()):
        n1 = LineupService(db).ingest_for_competition(6010, 6010)
    with patch("statsbombpy.sb.lineups", return_value=_lineups_dict()):
        n2 = LineupService(db).ingest_for_competition(6010, 6010)
    assert n1 == 1
    assert n2 == 0


def test_lineup_service_ingest_skips_fetch_error(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6011, season_id=6011)
    create_match(db, comp.id, statsbomb_id=60008)
    with patch("statsbombpy.sb.lineups", side_effect=Exception("fetch error")):
        n = LineupService(db).ingest_for_competition(6011, 6011)
    assert n == 0


# ── Frame360Service ────────────────────────────────────────────────────────

# IDs 6012-6013 / matches 60009-60010 reserved for frame360 service tests


def test_frame360_service_ingest(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6012, season_id=6012)
    create_match(db, comp.id, statsbomb_id=60009, match_status_360="available")
    with patch("statsbombpy.sb.frames", return_value=_frames_df("evt-frame-6012-001")):
        n = Frame360Service(db).ingest_for_competition(6012, 6012)
    assert n == 1


def test_frame360_service_ingest_idempotent(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6013, season_id=6013)
    create_match(db, comp.id, statsbomb_id=60010, match_status_360="available")
    with patch("statsbombpy.sb.frames", return_value=_frames_df("evt-frame-6013-001")):
        n1 = Frame360Service(db).ingest_for_competition(6013, 6013)
    with patch("statsbombpy.sb.frames", return_value=_frames_df("evt-frame-6013-001")):
        n2 = Frame360Service(db).ingest_for_competition(6013, 6013)
    assert n1 == 1
    assert n2 == 0
