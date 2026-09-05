import uuid
from typing import Any, cast

from sqlalchemy import Select, and_, union
from sqlalchemy.orm import aliased
from sqlmodel import Session, col, func, or_, select

from app.models.match import SoccerMatch
from app.models.team import Team


class MatchRepository:
    """Reads matches with their team names resolved through the FKs.

    Names come from joined `team` aliases as labelled columns rather than
    relationship traversal, so listing matches stays a single query.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def _events_exist_clause(self) -> Any:
        from app.models.event import Event

        return select(Event.id).where(col(Event.match_id) == SoccerMatch.id).exists()

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        competition_season_id: uuid.UUID | None = None,
        has_events: bool = False,
        team_name: str | None = None,
        team_id: uuid.UUID | None = None,
    ) -> tuple[list[tuple[SoccerMatch, str, str]], int, set[uuid.UUID]]:
        # Cast to Any because `aliased()` returns a runtime proxy whose
        # attributes are Column objects, while type checkers see the model's
        # declared types.
        home = cast(Any, aliased(Team))
        away = cast(Any, aliased(Team))

        stmt = (
            select(
                SoccerMatch, home.name.label("home_team"), away.name.label("away_team")
            )
            .join(home, col(SoccerMatch.home_team_id) == home.id)
            .join(away, col(SoccerMatch.away_team_id) == away.id)
        )
        count_stmt = (
            select(func.count())
            .select_from(SoccerMatch)
            .join(home, col(SoccerMatch.home_team_id) == home.id)
            .join(away, col(SoccerMatch.away_team_id) == away.id)
        )

        def both(clause: Any) -> None:
            nonlocal stmt, count_stmt
            stmt = stmt.where(clause)
            count_stmt = count_stmt.where(clause)

        if competition_season_id is not None:
            both(SoccerMatch.competition_season_id == competition_season_id)
        if team_id is not None:
            both(
                or_(
                    SoccerMatch.home_team_id == team_id,
                    SoccerMatch.away_team_id == team_id,
                )
            )
        if team_name is not None:
            words = team_name.strip().split()
            if words:
                # Every word must appear, in either team's name.
                both(
                    or_(
                        and_(*[home.name.ilike(f"%{w}%") for w in words]),
                        and_(*[away.name.ilike(f"%{w}%") for w in words]),
                    )
                )
        if has_events:
            both(self._events_exist_clause())

        count = self.session.exec(count_stmt).one()
        rows = self.session.exec(
            stmt.order_by(col(SoccerMatch.match_date).desc()).offset(skip).limit(limit)
        ).all()

        match_ids = [row[0].id for row in rows]
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

        return [(m, h, a) for m, h, a in rows], count, has_events_ids

    def list_distinct_teams(
        self,
        competition_season_id: uuid.UUID | None = None,
        has_events: bool = False,
    ) -> list[str]:
        """Distinct team names for the filter dropdown.

        Sourced from `team.name` so the names offered are exactly the ones the
        event filter can resolve.
        """

        def _team_select(fk: Any, alias: Any) -> Select[Any]:
            stmt: Select[Any] = (
                select(alias.name.label("team"))
                .select_from(SoccerMatch)
                .join(alias, fk == alias.id)
            )
            if competition_season_id is not None:
                stmt = stmt.where(
                    col(SoccerMatch.competition_season_id) == competition_season_id
                )
            if has_events:
                stmt = stmt.where(self._events_exist_clause())
            return stmt

        home = cast(Any, aliased(Team))
        away = cast(Any, aliased(Team))
        combined = union(
            _team_select(col(SoccerMatch.home_team_id), home),
            _team_select(col(SoccerMatch.away_team_id), away),
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
        """Matches of one competition season, addressed by the source's own ids."""
        from app.models.competition import Competition, CompetitionSeason, Season

        comp = self.session.exec(
            select(CompetitionSeason)
            .join(Competition, col(CompetitionSeason.competition_id) == Competition.id)
            .join(Season, col(CompetitionSeason.season_id) == Season.id)
            .where(
                Competition.external_id == str(competition_statsbomb_id),
                Season.external_id == str(season_id),
            )
        ).first()
        if comp is None:
            return []
        return list(
            self.session.exec(
                select(SoccerMatch).where(SoccerMatch.competition_season_id == comp.id)
            ).all()
        )

    def add(self, match: SoccerMatch) -> None:
        self.session.add(match)
