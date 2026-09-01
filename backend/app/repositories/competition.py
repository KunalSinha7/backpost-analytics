from typing import Any

from sqlalchemy import distinct, func
from sqlalchemy import select as sa_select
from sqlmodel import Session, col, select

from app.exceptions.competition import CompetitionNotFoundError
from app.models.competition import Competition, CompetitionSeason, Season


class CompetitionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        has_matches: bool = False,
        has_events: bool = False,
    ) -> tuple[list[tuple[CompetitionSeason, Competition, Season, int, int]], int]:
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
                .where(
                    col(SoccerMatch.competition_season_id) == col(CompetitionSeason.id)
                )
                .exists()
            )

        # One row per match that has at least one event. Joining against this
        # (rather than Event directly) keeps the join fan-out at one row per
        # match, so the match_count aggregate below stays truthful.
        matches_with_events = (
            select(col(Event.match_id).label("match_id")).distinct().subquery()
        )

        count_stmt = select(func.count()).select_from(CompetitionSeason)
        if has_matches:
            match_exists = (
                select(col(SoccerMatch.id))
                .where(
                    col(SoccerMatch.competition_season_id) == col(CompetitionSeason.id)
                )
                .exists()
            )
            count_stmt = count_stmt.where(match_exists)
        if has_events:
            count_stmt = count_stmt.where(_events_exist_clause())
        count = self.session.exec(count_stmt).one()

        # sqlalchemy.select rather than sqlmodel.select: SQLModel only
        # generates typed overloads for up to four entities, and this selects
        # five (three ORM entities plus two aggregates).
        stmt = (
            sa_select(
                CompetitionSeason,
                Competition,
                Season,
                func.count(distinct(col(SoccerMatch.id))).label("match_count"),
                func.count(distinct(matches_with_events.c.match_id)).label(
                    "event_match_count"
                ),
            )
            .join(Competition, col(CompetitionSeason.competition_id) == Competition.id)
            .join(Season, col(CompetitionSeason.season_ref_id) == Season.id)
            .outerjoin(
                SoccerMatch,
                col(SoccerMatch.competition_season_id) == col(CompetitionSeason.id),
            )
            .outerjoin(
                matches_with_events,
                matches_with_events.c.match_id == col(SoccerMatch.id),
            )
            .group_by(col(CompetitionSeason.id), col(Competition.id), col(Season.id))
            .order_by(col(Competition.name))
            .offset(skip)
            .limit(limit)
        )
        if has_matches:
            stmt = stmt.having(func.count(distinct(col(SoccerMatch.id))) > 0)
        if has_events:
            stmt = stmt.where(_events_exist_clause())

        rows = self.session.execute(stmt).all()
        # Hand back the session-attached ORM rows as-is. `model_validate` would
        # build a detached copy, dropping it out of the identity map and walking
        # `CompetitionSeason.matches` on the way — one extra query per row.
        return [
            (edition, competition, season, match_count, event_match_count)
            for edition, competition, season, match_count, event_match_count in rows
        ], count

    def get_existing_keys(self) -> set[tuple[int, int]]:
        return {
            (c.statsbomb_id, c.season_id)
            for c in self.session.exec(select(CompetitionSeason)).all()
        }

    def get_by_statsbomb_key(
        self, statsbomb_id: int, season_id: int
    ) -> CompetitionSeason:
        row = self.session.exec(
            select(CompetitionSeason).where(
                CompetitionSeason.statsbomb_id == statsbomb_id,
                CompetitionSeason.season_id == season_id,
            )
        ).first()
        if row is None:
            raise CompetitionNotFoundError(statsbomb_id, season_id)
        return row

    def add(self, competition: CompetitionSeason) -> None:
        self.session.add(competition)
