import uuid

from sqlmodel import Session, col, func, select

from app.models.lineup import Lineup
from app.models.player import Player
from app.models.team import Team


class LineupRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def has_lineups_for_match(self, match_id: uuid.UUID) -> bool:
        count = self.session.exec(
            select(func.count()).select_from(Lineup).where(Lineup.match_id == match_id)
        ).one()
        return count > 0

    def list_by_match(
        self, match_id: uuid.UUID
    ) -> tuple[list[tuple[Lineup, str, Player]], int]:
        """Squad list with team and player resolved in the same query.

        Ordering moves from the old `team_name` column to `team.name` — the
        same value, now with one source of truth. A squad is at most ~40 rows,
        so joining is cheap; no relationship traversal is involved.
        """
        count = self.session.exec(
            select(func.count()).select_from(Lineup).where(Lineup.match_id == match_id)
        ).one()
        rows = self.session.exec(
            select(Lineup, Team.name, Player)
            .join(Team, col(Lineup.team_id) == Team.id)
            .join(Player, col(Lineup.player_id) == Player.id)
            .where(Lineup.match_id == match_id)
            .order_by(col(Team.name), col(Lineup.jersey_number))
        ).all()
        return [
            (lineup, team_name, player) for lineup, team_name, player in rows
        ], count

    def add_batch(self, lineups: list[Lineup]) -> None:
        self.session.add_all(lineups)
