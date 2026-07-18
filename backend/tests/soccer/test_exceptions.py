from app.exceptions.competition import CompetitionNotFoundError
from app.exceptions.event import EventIngestError, StatsBombFetchError
from app.exceptions.match import MatchNotFoundError


def test_competition_not_found_error() -> None:
    err = CompetitionNotFoundError(statsbomb_id=43, season_id=3)
    assert "43" in str(err)
    assert "3" in str(err)
    assert err.statsbomb_id == 43
    assert err.season_id == 3
    assert isinstance(err, Exception)


def test_match_not_found_error() -> None:
    err = MatchNotFoundError(statsbomb_id=7576)
    assert "7576" in str(err)
    assert err.statsbomb_id == 7576
    assert isinstance(err, Exception)


def test_statsbomb_fetch_error() -> None:
    err = StatsBombFetchError(match_id=7576)
    assert "7576" in str(err)
    assert err.match_id == 7576
    assert isinstance(err, Exception)


def test_event_ingest_error() -> None:
    err = EventIngestError("something went wrong")
    assert "something went wrong" in str(err)
    assert isinstance(err, Exception)
