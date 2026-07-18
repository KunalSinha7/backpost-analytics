import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.models.lineup import LineupPublic, LineupsPublic
from app.repositories.lineup import LineupRepository

router = APIRouter(prefix="/lineups", tags=["soccer"])


@router.get("/", response_model=LineupsPublic, operation_id="readLineups")
def read_lineups(session: SessionDep, match_id: uuid.UUID) -> Any:
    repo = LineupRepository(session)
    rows, count = repo.list_by_match(match_id)
    return LineupsPublic(
        data=[LineupPublic.model_validate(r) for r in rows],
        count=count,
    )
