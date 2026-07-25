import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.models.frame360 import Frame360Public, Frames360Public
from app.services.frame360 import Frame360Service

router = APIRouter(prefix="/frames", tags=["soccer"])


@router.get("/", response_model=Frames360Public, operation_id="readFrames")
def read_frames(
    session: SessionDep,
    match_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    rows, count = Frame360Service(session).list_by_match(
        match_id, skip=skip, limit=limit
    )
    return Frames360Public(
        data=[Frame360Public.model_validate(r) for r in rows],
        count=count,
    )
