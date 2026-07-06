import logging
import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.models.match import SoccerMatchPublic, SoccerMatchesPublic
from app.repositories.match import MatchRepository

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
    repo = MatchRepository(session)
    rows, count = repo.list_all(
        skip=skip, limit=limit, competition_id=competition_id, has_events=has_events
    )
    return SoccerMatchesPublic(
        data=[SoccerMatchPublic.model_validate(r) for r in rows],
        count=count,
    )
