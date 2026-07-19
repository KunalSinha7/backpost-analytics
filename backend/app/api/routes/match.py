import logging
import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.models.match import SoccerMatchesPublic, SoccerMatchPublic
from app.repositories.match import MatchRepository
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
) -> Any:
    rows, count = MatchService(MatchRepository(session)).list_matches(
        skip=skip, limit=limit, competition_id=competition_id, has_events=has_events
    )
    return SoccerMatchesPublic(
        data=[SoccerMatchPublic.model_validate(r) for r in rows],
        count=count,
    )
