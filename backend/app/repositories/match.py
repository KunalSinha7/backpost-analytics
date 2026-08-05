import uuid
from typing import Any

from sqlalchemy import Select, and_, union
from sqlalchemy.orm import Mapped
from sqlmodel import Session, col, func, or_, select

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
        team_name: str | None = None,
    ) -> tuple[list[SoccerMatch], int, set[uuid.UUID]]:
        stmt = select(SoccerMatch)
        count_stmt = select(func.count()).select_from(SoccerMatch)
        if competition_id is not None:
            stmt = stmt.where(SoccerMatch.competition_id == competition_id)
            count_stmt = count_stmt.where(SoccerMatch.competition_id == competition_id)
        if team_name is not None:
            words = team_name.strip().split()
            if words:
                home_match = and_(
                    *[col(SoccerMatch.home_team).ilike(f"%{w}%") for w in words]
                )
                away_match = and_(
                    *[col(SoccerMatch.away_team).ilike(f"%{w}%") for w in words]
                )
                team_filter = or_(home_match, away_match)
                stmt = stmt.where(team_filter)
                count_stmt = count_stmt.where(team_filter)
        if has_events:
            from app.models.event import Event

            events_exist = (
                select(Event.id).where(Event.match_id == SoccerMatch.id).exists()
            )
            stmt = stmt.where(events_exist)
            count_stmt = count_stmt.where(events_exist)
        count = self.session.exec(count_stmt).one()
        rows = self.session.exec(
            stmt.order_by(col(SoccerMatch.match_date).desc()).offset(skip).limit(limit)
        ).all()

        match_ids = [r.id for r in rows]
        if match_ids:
            from app.models.event import Event

            has_events_ids: set[uuid.UUID] = set(
                self.session.exec(
                    select(Event.match_id)
                    .where(col(Event.match_id).in_(match_ids))
                    .distinct()
                ).all()
            )
        else:
            has_events_ids = set()

        return list(rows), count, has_events_ids

    def list_distinct_teams(
        self,
        competition_id: uuid.UUID | None = None,
        has_events: bool = False,
    ) -> list[str]:
        def _team_select(team_col: Mapped[str]) -> Select[Any]:
            stmt: Select[Any] = select(team_col.label("team"))
            if competition_id is not None:
                stmt = stmt.where(col(SoccerMatch.competition_id) == competition_id)
            if has_events:
                from app.models.event import Event

                events_exist = (
                    select(Event.id)
                    .where(col(Event.match_id) == SoccerMatch.id)
                    .exists()
                )
                stmt = stmt.where(events_exist)
            return stmt

        combined = union(
            _team_select(col(SoccerMatch.home_team)),
            _team_select(col(SoccerMatch.away_team)),
        ).subquery()
        rows = self.session.exec(
            select(combined.c.team).order_by(combined.c.team)
        ).all()
        return list(rows)

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
