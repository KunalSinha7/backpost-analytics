import uuid

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.exceptions.competition import CompetitionNotFoundError
from app.models.competition import Competition


class CompetitionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(
        self, skip: int = 0, limit: int = 100, has_matches: bool = False
    ) -> tuple[list[tuple[Competition, int]], int]:
        from app.models.match import SoccerMatch

        count_stmt = select(func.count()).select_from(Competition)
        if has_matches:
            match_exists = (
                select(SoccerMatch.id)
                .where(SoccerMatch.competition_id == Competition.id)
                .exists()
            )
            count_stmt = count_stmt.where(match_exists)
        count = self.session.exec(count_stmt).one()

        stmt = (
            select(Competition, func.count(SoccerMatch.id).label("match_count"))
            .outerjoin(SoccerMatch, SoccerMatch.competition_id == Competition.id)
            .group_by(Competition.id)
            .order_by(col(Competition.competition_name))
            .offset(skip)
            .limit(limit)
        )
        if has_matches:
            stmt = stmt.having(func.count(SoccerMatch.id) > 0)

        rows = self.session.exec(stmt).all()
        return [(Competition.model_validate(r[0]), r[1]) for r in rows], count

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
