import uuid

from sqlalchemy import func, text
from sqlmodel import Session, col, select

from app.models.competition import CompetitionSeason
from app.models.event import Event
from app.models.lineup import Lineup
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
            # Joined on the FK, not on `statsbomb_player_id == statsbomb_id`.
            # That soft integer join is precisely the "player identity split
            # three ways with no FK" §1.3 set out to remove; Phase 1 created the
            # FK and this query was the last caller still ignoring it. Verified
            # equivalent on the current data: 829 players, 0 disagreements.
            .outerjoin(
                Lineup,
                col(Lineup.player_id) == col(Player.id),
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

        Appearances counts matches where the player actually took the field — a
        named substitute who never came on has no stint, so they do not count.

        **Minutes are the union of on-pitch intervals, not the sum of stint
        durations.** Summing looks equivalent and is not: StatsBomb's lineup
        feed emits overlapping stints on some knockout matches, where the clock
        appears to restart mid-game. Messi's 2022 final reads:

            stint 1  from 00:00  (period 1) -> to 115:32 (period 4)
            stint 2  from 115:32 (period 4) -> to  28:11 (period 1)   <- backward
            stint 3  from 28:19  (period 1) -> to null, "Final Whistle"

        Summed, that is 213 minutes of a 126-minute match. Merging the
        intervals gives 125.97 — he played all of it, which is correct.

        Measured on the 2022 World Cup: 42 of 1,995 lineups contain a backward
        clock and 17 exceeded their own match length, the worst by 87 minutes.
        None of it showed up in the Ligue 1 data Phase 3 was validated against,
        because that season has no extra time — every match ended under 99
        minutes, so no stint could overlap far enough to notice.
        """
        sql = """
            WITH match_end AS (
                SELECT match_id, max(minute * 60 + second) AS end_s
                FROM event GROUP BY match_id
            ),
            stints AS (
                SELECT l.id AS lineup_id, l.match_id,
                       greatest(lp.from_seconds, 0) AS a,
                       least(lp.to_seconds, coalesce(me.end_s, lp.to_seconds)) AS b
                FROM lineup l
                JOIN lineup_position lp ON lp.lineup_id = l.id
                JOIN soccer_match m ON m.id = l.match_id
                JOIN competition_season cs ON cs.id = m.competition_season_id
                LEFT JOIN match_end me ON me.match_id = l.match_id
                WHERE l.player_id = :player_id
                  -- CAST(), not ::uuid — a `::` immediately after a bind
                  -- parameter stops SQLAlchemy recognising it as one.
                  AND (CAST(:season_id AS uuid) IS NULL
                       OR cs.season_ref_id = CAST(:season_id AS uuid))
            ),
            bounded AS (
                SELECT lineup_id, match_id, a, greatest(b, a) AS b FROM stints
            ),
            marked AS (
                SELECT *,
                       CASE WHEN a > coalesce(
                                max(b) OVER (PARTITION BY lineup_id ORDER BY a, b
                                             ROWS BETWEEN UNBOUNDED PRECEDING
                                                      AND 1 PRECEDING), -1)
                            THEN 1 ELSE 0 END AS is_new
                FROM bounded
            ),
            grouped AS (
                SELECT *, sum(is_new) OVER (PARTITION BY lineup_id ORDER BY a, b
                                            ROWS BETWEEN UNBOUNDED PRECEDING
                                                     AND CURRENT ROW) AS grp
                FROM marked
            ),
            merged AS (
                SELECT lineup_id, match_id, min(a) AS a, max(b) AS b
                FROM grouped GROUP BY lineup_id, match_id, grp
            )
            SELECT count(DISTINCT match_id) AS appearances,
                   coalesce(sum(b - a), 0) AS seconds
            FROM merged
        """
        appearances, seconds = self.session.execute(
            text(sql), {"player_id": player_id, "season_id": season_id}
        ).one()
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
