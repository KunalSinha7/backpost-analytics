from typing import Any

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.models.player import PlayerPublic, PlayersPublic
from app.services.player import PlayerService

router = APIRouter(prefix="/players", tags=["soccer"])


@router.get("/", response_model=PlayersPublic, operation_id="readPlayers")
def read_players(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    name_search: str | None = None,
) -> Any:
    rows, count = PlayerService(session).list_players(
        skip=skip, limit=limit, name_search=name_search
    )
    return PlayersPublic(
        data=[
            PlayerPublic.model_validate(player).model_copy(
                update={"match_count": match_count}
            )
            for player, match_count in rows
        ],
        count=count,
    )
