import uuid
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.soccer import (
    create_competition,
    create_event,
    create_frame,
    create_lineup,
    create_match,
)
from tests.utils.utils import get_superuser_token_headers


BASE = f"{settings.API_V1_STR}/soccer"


# ── Competitions ──────────────────────────────────────────────────────────


def test_read_competitions_empty(client: TestClient, superuser_token_headers: dict) -> None:
    response = client.get(f"{BASE}/competitions/", headers=superuser_token_headers)
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "count" in body


def test_read_competitions_with_data(
    client: TestClient, superuser_token_headers: dict, db: Session
) -> None:
    create_competition(db, statsbomb_id=8001, season_id=8001, competition_name="Route Test League")
    response = client.get(f"{BASE}/competitions/", headers=superuser_token_headers)
    assert response.status_code == 200
    names = [c["competition_name"] for c in response.json()["data"]]
    assert "Route Test League" in names


def test_ingest_soccer_data(client: TestClient, superuser_token_headers: dict) -> None:
    comps_df = pd.DataFrame(
        [
            {
                "competition_id": 8002,
                "season_id": 8002,
                "country_name": "Testland",
                "competition_name": "Ingest Test Cup",
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
    matches_df = pd.DataFrame([], columns=["match_id"])

    with (
        patch("statsbombpy.sb.competitions", return_value=comps_df),
        patch("statsbombpy.sb.matches", return_value=matches_df),
    ):
        response = client.post(f"{BASE}/competitions/ingest", headers=superuser_token_headers)

    assert response.status_code == 200
    body = response.json()
    assert "imported_competitions" in body
    assert "imported_matches" in body


def test_get_available_competitions(client: TestClient) -> None:
    avail_df = pd.DataFrame(
        [
            {
                "competition_id": 43,
                "season_id": 3,
                "country_name": "International",
                "competition_name": "FIFA World Cup",
                "competition_gender": "male",
                "competition_youth": False,
                "competition_international": True,
                "season_name": "2018",
                "match_updated": None,
                "match_available": None,
                "match_updated_360": None,
                "match_available_360": None,
            }
        ]
    )
    with patch("statsbombpy.sb.competitions", return_value=avail_df):
        response = client.get(f"{BASE}/competitions/available")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["competition_name"] == "FIFA World Cup"
    assert items[0]["has_360"] is False


# ── Matches ───────────────────────────────────────────────────────────────


def test_read_matches(client: TestClient, superuser_token_headers: dict, db: Session) -> None:
    comp = create_competition(db, statsbomb_id=8010, season_id=8010)
    create_match(db, comp.id, statsbomb_id=80010, home_team="Alpha", away_team="Beta")
    response = client.get(f"{BASE}/matches/", headers=superuser_token_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    teams = [(m["home_team"], m["away_team"]) for m in body["data"]]
    assert ("Alpha", "Beta") in teams


def test_read_matches_filter_by_competition(
    client: TestClient, superuser_token_headers: dict, db: Session
) -> None:
    comp = create_competition(db, statsbomb_id=8011, season_id=8011)
    create_match(db, comp.id, statsbomb_id=80011)
    response = client.get(
        f"{BASE}/matches/",
        params={"competition_id": str(comp.id)},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert all(m["competition_id"] == str(comp.id) for m in body["data"])


# ── Events ────────────────────────────────────────────────────────────────


def test_read_events(client: TestClient, superuser_token_headers: dict, db: Session) -> None:
    comp = create_competition(db, statsbomb_id=8020, season_id=8020)
    match = create_match(db, comp.id, statsbomb_id=80020)
    create_event(db, match.id, type_name="Pass")
    response = client.get(
        f"{BASE}/events/",
        params={"match_id": str(match.id)},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["data"][0]["type_name"] == "Pass"


def test_read_events_empty_match(
    client: TestClient, superuser_token_headers: dict
) -> None:
    response = client.get(
        f"{BASE}/events/",
        params={"match_id": str(uuid.uuid4())},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_ingest_events_accepted(
    client: TestClient, superuser_token_headers: dict
) -> None:
    response = client.post(
        f"{BASE}/events/ingest",
        params={"competition_statsbomb_id": 43, "season_id": 3},
        headers=superuser_token_headers,
    )
    assert response.status_code == 202
    assert "message" in response.json()


# ── Lineups ───────────────────────────────────────────────────────────────


def test_read_lineups(client: TestClient, superuser_token_headers: dict, db: Session) -> None:
    comp = create_competition(db, statsbomb_id=8030, season_id=8030)
    match = create_match(db, comp.id, statsbomb_id=80030)
    create_lineup(db, match.id, player_name="Messi", jersey_number=10, statsbomb_player_id=5503)
    response = client.get(
        f"{BASE}/lineups/",
        params={"match_id": str(match.id)},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["data"][0]["player_name"] == "Messi"


def test_read_lineups_empty(client: TestClient, superuser_token_headers: dict) -> None:
    response = client.get(
        f"{BASE}/lineups/",
        params={"match_id": str(uuid.uuid4())},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["count"] == 0


# ── Frames 360 ────────────────────────────────────────────────────────────


def test_read_frames(client: TestClient, superuser_token_headers: dict, db: Session) -> None:
    comp = create_competition(db, statsbomb_id=8040, season_id=8040)
    match = create_match(db, comp.id, statsbomb_id=80040)
    create_frame(db, match.id, "evt-route-frame-001")
    response = client.get(
        f"{BASE}/frames/",
        params={"match_id": str(match.id)},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["data"][0]["event_statsbomb_id"] == "evt-route-frame-001"


def test_read_frames_empty(client: TestClient, superuser_token_headers: dict) -> None:
    response = client.get(
        f"{BASE}/frames/",
        params={"match_id": str(uuid.uuid4())},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["count"] == 0
