import uuid

from sqlmodel import Session, col, func, select

from app.models.lineup import Lineup


class LineupRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def has_lineups_for_match(self, match_id: uuid.UUID) -> bool:
        count = self.session.exec(
            select(func.count()).select_from(Lineup).where(Lineup.match_id == match_id)
        ).one()
        return count > 0

    def list_by_match(self, match_id: uuid.UUID) -> tuple[list[Lineup], int]:
        count = self.session.exec(
            select(func.count()).select_from(Lineup).where(Lineup.match_id == match_id)
        ).one()
        players = self.session.exec(
            select(Lineup)
            .where(Lineup.match_id == match_id)
            .order_by(col(Lineup.team_name), col(Lineup.jersey_number))
        ).all()
        return list(players), count

    def add_batch(self, lineups: list[Lineup]) -> None:
        self.session.add_all(lineups)
