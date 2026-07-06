import uuid

from sqlmodel import Session, col, func, select

from app.models.match import SoccerMatch


class MatchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        competition_id: uuid.UUID | None = None,
        has_events: bool = False,
    ) -> tuple[list[SoccerMatch], int]:
        stmt = select(SoccerMatch)
        count_stmt = select(func.count()).select_from(SoccerMatch)
        if competition_id is not None:
            stmt = stmt.where(SoccerMatch.competition_id == competition_id)
            count_stmt = count_stmt.where(SoccerMatch.competition_id == competition_id)
        if has_events:
            from app.models.event import Event

            events_exist = select(Event.id).where(Event.match_id == SoccerMatch.id).exists()
            stmt = stmt.where(events_exist)
            count_stmt = count_stmt.where(events_exist)
        count = self.session.exec(count_stmt).one()
        rows = self.session.exec(
            stmt.order_by(col(SoccerMatch.match_date).desc()).offset(skip).limit(limit)
        ).all()
        return list(rows), count

    def get_existing_statsbomb_ids(self) -> set[int]:
        return {m.statsbomb_id for m in self.session.exec(select(SoccerMatch)).all()}

    def list_for_competition(
        self, competition_statsbomb_id: int, season_id: int
    ) -> list[SoccerMatch]:
        from app.models.competition import Competition

        comp = self.session.exec(
            select(Competition).where(
                Competition.statsbomb_id == competition_statsbomb_id,
                Competition.season_id == season_id,
            )
        ).first()
        if comp is None:
            return []
        return list(
            self.session.exec(
                select(SoccerMatch).where(SoccerMatch.competition_id == comp.id)
            ).all()
        )

    def add(self, match: SoccerMatch) -> None:
        self.session.add(match)
