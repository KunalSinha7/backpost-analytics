import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import SessionDep
from app.models.player import PlayerPublic, PlayerSeasonStats, PlayersPublic
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


@router.get(
    "/{player_id}/stats",
    response_model=PlayerSeasonStats,
    operation_id="readPlayerSeasonStats",
)
def read_player_season_stats(
    session: SessionDep,
    player_id: uuid.UUID,
    season_id: uuid.UUID | None = None,
) -> Any:
    """Season stats for one player, with per-90 rates.

    `season_id` is the `season` entity's id (Phase 2), not StatsBomb's integer.
    Omit it for career totals across everything ingested.
    """
    stats = PlayerService(session).get_season_stats(player_id, season_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return stats
