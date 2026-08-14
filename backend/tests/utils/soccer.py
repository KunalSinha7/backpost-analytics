"""Fixture builders for the soccer domain.

After the Phase 4 contract step the name columns are gone, so these helpers
resolve entities instead of writing strings. They deliberately keep their old
signatures — callers still pass `home_team="Home FC"` — and get-or-create the
`team` / `player` / `competition` / `season` rows behind the scenes. Keeping the
call sites stable is what let the contract phase land without rewriting what
every test was actually asserting.
"""

import uuid
from hashlib import blake2b

from sqlmodel import Session, select

from app.models.competition import CompetitionSeason
from app.models.event import Event
from app.models.frame360 import Frame360
from app.models.lineup import Lineup
from app.models.match import SoccerMatch
from app.models.player import Player
from app.models.team import Team
from app.services.resolver import EntityResolver


def _stable_external_id(name: str) -> str:
    """A deterministic external id for a fixture name.

    Tests name teams, they do not id them, but identity is
    `(source_id, external_id)` now. Deriving the id from the name keeps
    "Home FC" the same team across calls without a shared counter, and keeps
    runs reproducible.
    """
    # 3 bytes, not 4: `player.statsbomb_id` is a Postgres INTEGER, and a
    # 4-byte digest overflows its 2,147,483,647 ceiling.
    return str(int(blake2b(name.encode(), digest_size=3).hexdigest(), 16))


def create_team(db: Session, name: str, external_id: object = None) -> Team:
    resolver = EntityResolver(db)
    team = resolver.resolve_team(
        external_id if external_id is not None else _stable_external_id(name),
        name,
        authoritative_name=True,
    )
    db.commit()
    assert team is not None
    return team


def create_player(db: Session, name: str, statsbomb_id: int | None = None) -> Player:
    """Get-or-create a fixture player.

    When no id is given, an existing player with the same name wins. Production
    identity is `(source_id, external_id)` and never the name — but fixtures
    address players *by* name, and deriving a separate id from the name would
    silently create a second player for someone a lineup already introduced.
    That is how a season-stats fixture ended up with the events attached to one
    player and the minutes to another.
    """
    if statsbomb_id is None:
        existing = db.exec(select(Player).where(Player.name == name)).first()
        if existing is not None:
            return existing
    resolver = EntityResolver(db)
    player = resolver.resolve_player(
        statsbomb_id if statsbomb_id is not None else _stable_external_id(name), name
    )
    db.commit()
    assert player is not None
    return player


def create_competition(db: Session, **kwargs: object) -> CompetitionSeason:
    """An *edition* row plus the competition and season it points at.

    After the Phase 2 split `Competition` means the timeless entity, so the
    thing tests want — one row per (competition, season), which is what
    /competitions serves — is a CompetitionSeason.
    """
    statsbomb_id = int(kwargs.get("statsbomb_id", 999))  # type: ignore[arg-type]
    season_id = int(kwargs.get("season_id", 999))  # type: ignore[arg-type]
    resolver = EntityResolver(db)
    competition = resolver.resolve_competition(
        statsbomb_id,
        str(kwargs.get("competition_name", "Test League")),
        country_name=str(kwargs.get("country_name", "Test Country")),
        gender=str(kwargs.get("competition_gender", "male")),
        is_youth=bool(kwargs.get("competition_youth", False)),
        is_international=bool(kwargs.get("competition_international", False)),
    )
    season = resolver.resolve_season(season_id, str(kwargs.get("season_name", "2099")))
    assert competition is not None and season is not None

    comp = CompetitionSeason(
        statsbomb_id=statsbomb_id,
        season_id=season_id,
        competition_id=competition.id,
        season_ref_id=season.id,
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp


def create_match(
    db: Session, competition_season_id: uuid.UUID, **kwargs: object
) -> SoccerMatch:
    home = create_team(db, str(kwargs.get("home_team", "Home FC")))
    away = create_team(db, str(kwargs.get("away_team", "Away FC")))
    match = SoccerMatch(
        statsbomb_id=kwargs.get("statsbomb_id", 88888),
        competition_season_id=competition_season_id,
        match_date=kwargs.get("match_date", "2099-01-01"),
        home_team_id=home.id,
        away_team_id=away.id,
        home_score=kwargs.get("home_score", 1),
        away_score=kwargs.get("away_score", 0),
        match_status_360=kwargs.get("match_status_360", None),
        raw=kwargs.get("raw"),
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def create_event(db: Session, match_id: uuid.UUID, **kwargs: object) -> Event:
    team = create_team(db, str(kwargs.get("team", "Home FC")))
    possession_team_name = kwargs.get("possession_team_name")
    possession_team = (
        create_team(db, str(possession_team_name)) if possession_team_name else team
    )
    player_name = kwargs.get("player")
    player = create_player(db, str(player_name)) if player_name else None
    recipient_name = kwargs.get("pass_recipient")
    recipient = create_player(db, str(recipient_name)) if recipient_name else None

    event = Event(
        statsbomb_id=kwargs.get("statsbomb_id", str(uuid.uuid4())),
        match_id=match_id,
        index=kwargs.get("index", 1),
        period=kwargs.get("period", 1),
        minute=kwargs.get("minute", 0),
        second=kwargs.get("second", 0),
        type_name=kwargs.get("type_name", "Kick Off"),
        team_id=team.id,
        possession_team_id=possession_team.id,
        player_id=player.id if player else None,
        pass_recipient_id=recipient.id if recipient else None,
        possession=kwargs.get("possession"),
        end_location_x=kwargs.get("end_location_x"),
        end_location_y=kwargs.get("end_location_y"),
        raw_event=kwargs.get("raw_event") or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_lineup(db: Session, match_id: uuid.UUID, **kwargs: object) -> Lineup:
    team = create_team(db, str(kwargs.get("team_name", "Home FC")))
    statsbomb_player_id = int(kwargs.get("statsbomb_player_id", 1001))  # type: ignore[arg-type]
    player = create_player(
        db, str(kwargs.get("player_name", "Test Player")), statsbomb_player_id
    )
    nickname = kwargs.get("player_nickname")
    country = kwargs.get("country_name")
    if nickname:
        player.nickname = str(nickname)
    if country:
        player.nationality = str(country)

    lineup = Lineup(
        match_id=match_id,
        team_id=team.id,
        player_id=player.id,
        statsbomb_player_id=statsbomb_player_id,
        jersey_number=kwargs.get("jersey_number", 10),
        started=kwargs.get("started", True),
        raw=kwargs.get("raw"),
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


def team_named(db: Session, name: str) -> Team | None:
    return db.exec(select(Team).where(Team.name == name)).first()
