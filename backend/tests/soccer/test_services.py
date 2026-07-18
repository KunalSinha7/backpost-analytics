from unittest.mock import patch

import pandas as pd
import pytest
from sqlmodel import Session

from app.exceptions.event import StatsBombFetchError
from app.repositories.competition import CompetitionRepository
from app.repositories.event import EventRepository
from app.repositories.frame360 import Frame360Repository
from app.repositories.lineup import LineupRepository
from app.repositories.match import MatchRepository
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
    with patch("statsbombpy.sb.competitions", return_value=_competitions_df(6001, 6001)):
        repo = CompetitionRepository(db)
        n, comps = CompetitionService(repo).ingest()
    assert n >= 1
    assert any(c.statsbomb_id == 6001 for c in comps)


def test_competition_service_ingest_idempotent(db: Session) -> None:
    comps_df = _competitions_df(6002, 6002)
    with patch("statsbombpy.sb.competitions", return_value=comps_df):
        repo = CompetitionRepository(db)
        svc = CompetitionService(repo)
        n1, _ = svc.ingest()
    with patch("statsbombpy.sb.competitions", return_value=comps_df):
        n2, _ = svc.ingest()
    assert n1 >= 1
    assert n2 == 0


# ── MatchService ───────────────────────────────────────────────────────────

# IDs 6003-6005 reserved for match service tests


def test_match_service_ingest(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6003, season_id=6003)
    with patch("statsbombpy.sb.matches", return_value=_matches_df(60001)):
        repo = MatchRepository(db)
        n = MatchService(repo).ingest([comp])
    assert n >= 1


def test_match_service_ingest_skips_fetch_error(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6004, season_id=6004)
    with patch("statsbombpy.sb.matches", side_effect=Exception("network error")):
        repo = MatchRepository(db)
        n = MatchService(repo).ingest([comp])
    assert n == 0


def test_match_service_ingest_idempotent(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6005, season_id=6005)
    with patch("statsbombpy.sb.matches", return_value=_matches_df(60002)):
        repo = MatchRepository(db)
        svc = MatchService(repo)
        n1 = svc.ingest([comp])
    with patch("statsbombpy.sb.matches", return_value=_matches_df(60002)):
        n2 = svc.ingest([comp])
    assert n1 >= 1
    assert n2 == 0


# ── EventService ───────────────────────────────────────────────────────────

# IDs 6006-6008 / matches 60003-60005 reserved for event service tests


def test_event_service_ingest(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6006, season_id=6006)
    create_match(db, comp.id, statsbomb_id=60003)
    with patch("statsbombpy.sb.events", return_value=_events_df("evt-svc-6006-001")):
        svc = EventService(EventRepository(db), MatchRepository(db))
        n = svc.ingest_for_competition(6006, 6006, db)
    assert n == 1


def test_event_service_ingest_raises_on_fetch_error(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6007, season_id=6007)
    create_match(db, comp.id, statsbomb_id=60004)
    with patch("statsbombpy.sb.events", side_effect=Exception("fetch failed")):
        svc = EventService(EventRepository(db), MatchRepository(db))
        with pytest.raises(StatsBombFetchError):
            svc.ingest_for_competition(6007, 6007, db)


def test_event_service_ingest_idempotent(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6008, season_id=6008)
    create_match(db, comp.id, statsbomb_id=60005)
    with patch("statsbombpy.sb.events", return_value=_events_df("evt-svc-6008-001")):
        svc = EventService(EventRepository(db), MatchRepository(db))
        n1 = svc.ingest_for_competition(6008, 6008, db)
    with patch("statsbombpy.sb.events", return_value=_events_df("evt-svc-6008-001")):
        n2 = svc.ingest_for_competition(6008, 6008, db)
    assert n1 == 1
    assert n2 == 0


# ── LineupService ──────────────────────────────────────────────────────────

# IDs 6009-6011 / matches 60006-60008 reserved for lineup service tests


def test_lineup_service_ingest(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6009, season_id=6009)
    create_match(db, comp.id, statsbomb_id=60006)
    with patch("statsbombpy.sb.lineups", return_value=_lineups_dict()):
        svc = LineupService(LineupRepository(db), MatchRepository(db))
        n = svc.ingest_for_competition(6009, 6009, db)
    assert n == 1


def test_lineup_service_ingest_idempotent(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6010, season_id=6010)
    create_match(db, comp.id, statsbomb_id=60007)
    with patch("statsbombpy.sb.lineups", return_value=_lineups_dict()):
        svc = LineupService(LineupRepository(db), MatchRepository(db))
        n1 = svc.ingest_for_competition(6010, 6010, db)
    with patch("statsbombpy.sb.lineups", return_value=_lineups_dict()):
        n2 = svc.ingest_for_competition(6010, 6010, db)
    assert n1 == 1
    assert n2 == 0


def test_lineup_service_ingest_skips_fetch_error(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6011, season_id=6011)
    create_match(db, comp.id, statsbomb_id=60008)
    with patch("statsbombpy.sb.lineups", side_effect=Exception("fetch error")):
        svc = LineupService(LineupRepository(db), MatchRepository(db))
        n = svc.ingest_for_competition(6011, 6011, db)
    assert n == 0


# ── Frame360Service ────────────────────────────────────────────────────────

# IDs 6012-6013 / matches 60009-60010 reserved for frame360 service tests


def test_frame360_service_ingest(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6012, season_id=6012)
    create_match(db, comp.id, statsbomb_id=60009, match_status_360="available")
    with patch("statsbombpy.sb.frames", return_value=_frames_df("evt-frame-6012-001")):
        svc = Frame360Service(Frame360Repository(db), MatchRepository(db))
        n = svc.ingest_for_competition(6012, 6012, db)
    assert n == 1


def test_frame360_service_ingest_idempotent(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=6013, season_id=6013)
    create_match(db, comp.id, statsbomb_id=60010, match_status_360="available")
    with patch("statsbombpy.sb.frames", return_value=_frames_df("evt-frame-6013-001")):
        svc = Frame360Service(Frame360Repository(db), MatchRepository(db))
        n1 = svc.ingest_for_competition(6013, 6013, db)
    with patch("statsbombpy.sb.frames", return_value=_frames_df("evt-frame-6013-001")):
        n2 = svc.ingest_for_competition(6013, 6013, db)
    assert n1 == 1
    assert n2 == 0
