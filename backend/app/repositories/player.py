import uuid

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models.competition import CompetitionSeason
from app.models.event import Event
from app.models.lineup import Lineup
from app.models.lineup_position import LineupPosition
from app.models.match import SoccerMatch
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

    def get_by_id(self, player_id: uuid.UUID) -> Player | None:
        return self.session.get(Player, player_id)

    def season_minutes_and_appearances(
        self,
        player_id: uuid.UUID,
        season_id: uuid.UUID | None = None,
    ) -> tuple[int, float]:
        """Matches played and minutes on the pitch, optionally scoped to a season.

        Appearances counts matches where the player actually took the field —
        a named substitute who never came on has no stint, so they do not count.
        Minutes come from `lineup_position`, which is the whole reason Phase 3
        exists: before it, that number lived inside a JSON array and could not
        be aggregated at all.
        """
        stmt = (
            select(
                func.count(func.distinct(col(Lineup.match_id))),
                func.coalesce(
                    func.sum(
                        col(LineupPosition.to_seconds)
                        - col(LineupPosition.from_seconds)
                    ),
                    0,
                ),
            )
            .select_from(Lineup)
            .join(LineupPosition, col(LineupPosition.lineup_id) == col(Lineup.id))
            .join(SoccerMatch, col(SoccerMatch.id) == col(Lineup.match_id))
            .join(
                CompetitionSeason,
                col(CompetitionSeason.id) == col(SoccerMatch.competition_season_id),
            )
            .where(col(Lineup.player_id) == player_id)
        )
        if season_id is not None:
            stmt = stmt.where(col(CompetitionSeason.season_ref_id) == season_id)
        appearances, seconds = self.session.exec(stmt).one()
        return int(appearances or 0), round(float(seconds or 0) / 60.0, 2)

    def season_event_counts(
        self,
        player_id: uuid.UUID,
        season_id: uuid.UUID | None = None,
    ) -> list[tuple[str, int]]:
        """Event counts by type. Uses ix_event_player_match (player_id, match_id)."""
        stmt = (
            select(col(Event.type_name), func.count())
            .select_from(Event)
            .join(SoccerMatch, col(SoccerMatch.id) == col(Event.match_id))
            .join(
                CompetitionSeason,
                col(CompetitionSeason.id) == col(SoccerMatch.competition_season_id),
            )
            .where(col(Event.player_id) == player_id)
            .group_by(col(Event.type_name))
            .order_by(func.count().desc())
        )
        if season_id is not None:
            stmt = stmt.where(col(CompetitionSeason.season_ref_id) == season_id)
        return [(name, int(count)) for name, count in self.session.exec(stmt).all()]
