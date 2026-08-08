from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models.lineup import Lineup
from app.models.player import Player


class PlayerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        name_search: str | None = None,
    ) -> tuple[list[tuple[Player, int]], int]:
        count_stmt = select(func.count()).select_from(Player)
        if name_search:
            count_stmt = count_stmt.where(col(Player.name).ilike(f"%{name_search}%"))
        count = self.session.exec(count_stmt).one()

        stmt = (
            select(Player, func.count(col(Lineup.id)).label("match_count"))
            .outerjoin(
                Lineup,
                col(Lineup.statsbomb_player_id) == col(Player.statsbomb_id),
            )
            .group_by(col(Player.id))
            .order_by(col(Player.name))
            .offset(skip)
            .limit(limit)
        )
        if name_search:
            stmt = stmt.where(col(Player.name).ilike(f"%{name_search}%"))

        rows = self.session.exec(stmt).all()
        # Session-attached ORM row, not a `Player.model_validate` copy — see the
        # note in CompetitionRepository.list_all.
        return [(player, match_count) for player, match_count in rows], count

    def upsert_from_lineup_batch(self, lineups: list[Lineup]) -> int:
        existing_ids = set(self.session.exec(select(col(Player.statsbomb_id))).all())
        new_players = []
        seen: set[int] = set()
        for lineup in lineups:
            sid = lineup.statsbomb_player_id
            if sid not in existing_ids and sid not in seen:
                seen.add(sid)
                new_players.append(
                    Player(
                        statsbomb_id=sid,
                        name=lineup.player_name,
                        nickname=lineup.player_nickname,
                        nationality=lineup.country_name,
                    )
                )
        if new_players:
            self.session.add_all(new_players)
        return len(new_players)
