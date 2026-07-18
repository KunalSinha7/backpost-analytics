import uuid

import pytest
from sqlmodel import Session

from app.exceptions.competition import CompetitionNotFoundError
from app.repositories.competition import CompetitionRepository
from app.repositories.event import EventRepository
from app.repositories.frame360 import Frame360Repository
from app.repositories.lineup import LineupRepository
from app.repositories.match import MatchRepository
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
    assert any(c.statsbomb_id == 1001 for c in rows)


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


# ── MatchRepository ────────────────────────────────────────────────────────


def test_match_list_all(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=2001, season_id=2001)
    create_match(db, comp.id, statsbomb_id=20001)
    repo = MatchRepository(db)
    rows, count = repo.list_all()
    assert count >= 1
    assert any(m.statsbomb_id == 20001 for m in rows)


def test_match_list_all_filter_by_competition(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=2002, season_id=2002)
    create_match(db, comp.id, statsbomb_id=20002)
    repo = MatchRepository(db)
    rows, count = repo.list_all(competition_id=comp.id)
    assert count >= 1
    assert all(m.competition_id == comp.id for m in rows)


def test_match_list_all_has_events_filter(db: Session) -> None:
    comp = create_competition(db, statsbomb_id=2003, season_id=2003)
    match_with = create_match(db, comp.id, statsbomb_id=20003)
    match_without = create_match(db, comp.id, statsbomb_id=20004)
    create_event(db, match_with.id)

    repo = MatchRepository(db)
    rows, count = repo.list_all(has_events=True)
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
    create_lineup(db, match.id, player_name="Alice", jersey_number=1, statsbomb_player_id=4101)
    create_lineup(db, match.id, player_name="Bob", jersey_number=2, statsbomb_player_id=4102)

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
