from sqlmodel import Session, col, func, select

from app.exceptions.competition import CompetitionNotFoundError
from app.models.competition import Competition


class CompetitionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self, skip: int = 0, limit: int = 100) -> tuple[list[Competition], int]:
        count = self.session.exec(select(func.count()).select_from(Competition)).one()
        rows = self.session.exec(
            select(Competition)
            .order_by(col(Competition.competition_name))
            .offset(skip)
            .limit(limit)
        ).all()
        return list(rows), count

    def get_existing_keys(self) -> set[tuple[int, int]]:
        return {
            (c.statsbomb_id, c.season_id)
            for c in self.session.exec(select(Competition)).all()
        }

    def get_by_statsbomb_key(self, statsbomb_id: int, season_id: int) -> Competition:
        row = self.session.exec(
            select(Competition).where(
                Competition.statsbomb_id == statsbomb_id,
                Competition.season_id == season_id,
            )
        ).first()
        if row is None:
            raise CompetitionNotFoundError(statsbomb_id, season_id)
        return row

    def add(self, competition: Competition) -> None:
        self.session.add(competition)
