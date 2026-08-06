import logging
import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.models.match import SoccerMatchesPublic, SoccerMatchPublic, SoccerTeamsPublic
from app.services.match import MatchService

router = APIRouter(prefix="/matches", tags=["soccer"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=SoccerMatchesPublic, operation_id="readMatches")
def read_matches(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    competition_id: uuid.UUID | None = None,
    has_events: bool = False,
    team_name: str | None = None,
) -> Any:
    rows, count, has_events_ids = MatchService(session).list_matches(
        skip=skip,
        limit=limit,
        competition_id=competition_id,
        has_events=has_events,
        team_name=team_name,
    )
    return SoccerMatchesPublic(
        data=[
            SoccerMatchPublic.model_validate(r).model_copy(
                update={"has_events": r.id in has_events_ids}
            )
            for r in rows
        ],
        count=count,
    )


@router.get("/teams", response_model=SoccerTeamsPublic, operation_id="readMatchTeams")
def read_match_teams(
    session: SessionDep,
    competition_id: uuid.UUID | None = None,
    has_events: bool = False,
) -> Any:
    teams = MatchService(session).list_teams(
        competition_id=competition_id, has_events=has_events
    )
    return SoccerTeamsPublic(data=teams)
