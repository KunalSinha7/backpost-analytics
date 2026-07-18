import uuid

from sqlmodel import Session

from app.models.competition import Competition
from app.models.event import Event
from app.models.frame360 import Frame360
from app.models.lineup import Lineup
from app.models.match import SoccerMatch


def create_competition(db: Session, **kwargs: object) -> Competition:
    comp = Competition(
        statsbomb_id=kwargs.get("statsbomb_id", 999),
        season_id=kwargs.get("season_id", 999),
        country_name=kwargs.get("country_name", "Test Country"),
        competition_name=kwargs.get("competition_name", "Test League"),
        competition_gender=kwargs.get("competition_gender", "male"),
        competition_youth=kwargs.get("competition_youth", False),
        competition_international=kwargs.get("competition_international", False),
        season_name=kwargs.get("season_name", "2099"),
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp


def create_match(
    db: Session, competition_id: uuid.UUID, **kwargs: object
) -> SoccerMatch:
    match = SoccerMatch(
        statsbomb_id=kwargs.get("statsbomb_id", 88888),
        competition_id=competition_id,
        match_date=kwargs.get("match_date", "2099-01-01"),
        home_team=kwargs.get("home_team", "Home FC"),
        away_team=kwargs.get("away_team", "Away FC"),
        home_score=kwargs.get("home_score", 1),
        away_score=kwargs.get("away_score", 0),
        match_status_360=kwargs.get("match_status_360", None),
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def create_event(db: Session, match_id: uuid.UUID, **kwargs: object) -> Event:
    event = Event(
        statsbomb_id=kwargs.get("statsbomb_id", str(uuid.uuid4())),
        match_id=match_id,
        index=kwargs.get("index", 1),
        period=kwargs.get("period", 1),
        minute=kwargs.get("minute", 0),
        second=kwargs.get("second", 0),
        type_name=kwargs.get("type_name", "Kick Off"),
        team=kwargs.get("team", "Home FC"),
        raw_event={},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_lineup(db: Session, match_id: uuid.UUID, **kwargs: object) -> Lineup:
    lineup = Lineup(
        match_id=match_id,
        team_name=kwargs.get("team_name", "Home FC"),
        statsbomb_player_id=kwargs.get("statsbomb_player_id", 1001),
        player_name=kwargs.get("player_name", "Test Player"),
        jersey_number=kwargs.get("jersey_number", 10),
        started=kwargs.get("started", True),
    )
    db.add(lineup)
    db.commit()
    db.refresh(lineup)
    return lineup


def create_frame(db: Session, match_id: uuid.UUID, event_statsbomb_id: str) -> Frame360:
    frame = Frame360(
        match_id=match_id,
        event_statsbomb_id=event_statsbomb_id,
        visible_area=[0.0, 80.0, 120.0, 80.0],
        freeze_frame=[],
    )
    db.add(frame)
    db.commit()
    db.refresh(frame)
    return frame
