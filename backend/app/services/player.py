from sqlmodel import Session

from app.models.player import Player
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
