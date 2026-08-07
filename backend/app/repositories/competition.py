from typing import Any

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.exceptions.competition import CompetitionNotFoundError
from app.models.competition import Competition


class CompetitionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        has_matches: bool = False,
        has_events: bool = False,
    ) -> tuple[list[tuple[Competition, int]], int]:
        from app.models.event import Event
        from app.models.match import SoccerMatch

        def _events_exist_clause() -> Any:
            # A competition "has events" if at least one of its matches has
            # at least one event — has_matches alone isn't enough, since the
            # full competition/match catalog is ingested up front while
            # events are ingested per competition/season separately.
            # Flattened into one EXISTS(JOIN) rather than nested EXISTS(EXISTS):
            # SoccerMatch would otherwise be both the middle query's FROM and
            # the inner query's correlation target, which SQLAlchemy can't
            # auto-correlate unambiguously.
            return (
                select(col(SoccerMatch.id))
                .join(Event, col(Event.match_id) == col(SoccerMatch.id))
                .where(col(SoccerMatch.competition_id) == col(Competition.id))
                .exists()
            )

        count_stmt = select(func.count()).select_from(Competition)
        if has_matches:
            match_exists = (
                select(col(SoccerMatch.id))
                .where(col(SoccerMatch.competition_id) == col(Competition.id))
                .exists()
            )
            count_stmt = count_stmt.where(match_exists)
        if has_events:
            count_stmt = count_stmt.where(_events_exist_clause())
        count = self.session.exec(count_stmt).one()

        stmt = (
            select(Competition, func.count(col(SoccerMatch.id)).label("match_count"))
            .outerjoin(
                SoccerMatch,
                col(SoccerMatch.competition_id) == col(Competition.id),
            )
            .group_by(col(Competition.id))
            .order_by(col(Competition.competition_name))
            .offset(skip)
            .limit(limit)
        )
        if has_matches:
            stmt = stmt.having(func.count(col(SoccerMatch.id)) > 0)
        if has_events:
            stmt = stmt.where(_events_exist_clause())

        rows = self.session.exec(stmt).all()
        # Hand back the session-attached ORM row as-is. `Competition.model_validate`
        # would build a detached copy, dropping it out of the identity map and
        # walking `Competition.matches` on the way — one extra query per row.
        return [(competition, match_count) for competition, match_count in rows], count

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
