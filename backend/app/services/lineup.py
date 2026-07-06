import logging

from sqlmodel import Session

from app.models.lineup import Lineup
from app.repositories.lineup import LineupRepository
from app.repositories.match import MatchRepository
from app.utils.statsbomb import StatsBombLineupPlayerRow

logger = logging.getLogger(__name__)


class LineupService:
    def __init__(self, lineup_repo: LineupRepository, match_repo: MatchRepository) -> None:
        self.lineup_repo = lineup_repo
        self.match_repo = match_repo

    def ingest_for_competition(
        self, competition_statsbomb_id: int, season_id: int, session: Session
    ) -> int:
        from statsbombpy import sb  # type: ignore[import-untyped]

        matches = self.match_repo.list_for_competition(competition_statsbomb_id, season_id)
        total_imported = 0

        for match in matches:
            if self.lineup_repo.has_lineups_for_match(match.id):
                continue

            try:
                lineups = sb.lineups(match_id=match.statsbomb_id)
            except Exception:
                logger.warning("Could not fetch lineups for match %s", match.statsbomb_id)
                continue

            batch: list[Lineup] = []
            for team_name, players_df in lineups.items():
                for _, row in players_df.iterrows():
                    player_row = StatsBombLineupPlayerRow.model_validate(row.to_dict())
                    lineup = Lineup(
                        match_id=match.id,
                        team_name=team_name,
                        statsbomb_player_id=player_row.player_id,
                        player_name=player_row.player_name,
                        player_nickname=player_row.player_nickname,
                        jersey_number=player_row.jersey_number,
                        country_name=player_row.country,
                        started=player_row.is_starter(),
                    )
                    batch.append(lineup)

            self.lineup_repo.add_batch(batch)
            session.commit()
            total_imported += len(batch)
            logger.info(
                "Lineups ingested: match_id=%s, players=%d", match.statsbomb_id, len(batch)
            )

        return total_imported
