import uuid

from sqlmodel import Session

from app.models.player import Player, PlayerSeasonStats, PlayerStatLine
from app.repositories.player import PlayerRepository


class PlayerService:
    def __init__(self, session: Session) -> None:
        self.repo = PlayerRepository(session)

    def list_players(
        self,
        skip: int = 0,
        limit: int = 100,
        name_search: str | None = None,
    ) -> tuple[list[tuple[Player, int]], int]:
        return self.repo.list_all(skip=skip, limit=limit, name_search=name_search)

    def get_season_stats(
        self,
        player_id: uuid.UUID,
        season_id: uuid.UUID | None = None,
    ) -> PlayerSeasonStats | None:
        player = self.repo.get_by_id(player_id)
        if player is None:
            return None

        appearances, minutes = self.repo.season_minutes_and_appearances(
            player_id, season_id
        )
        counts = self.repo.season_event_counts(player_id, season_id)

        # Per-90 is undefined at zero minutes rather than infinite. Reporting 0
        # would read as "did nothing" for a player who was never on the pitch.
        def per_90(count: int) -> float:
            if minutes <= 0:
                return 0.0
            return round(count * 90.0 / minutes, 2)

        return PlayerSeasonStats(
            player_id=player.id,
            player_name=player.name,
            season_id=season_id,
            appearances=appearances,
            minutes_played=minutes,
            stats=[
                PlayerStatLine(type_name=name, count=count, per_90=per_90(count))
                for name, count in counts
            ],
        )
