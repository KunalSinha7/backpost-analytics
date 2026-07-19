import logging
import uuid

from app.models.competition import Competition
from app.models.match import SoccerMatch
from app.repositories.match import MatchRepository
from app.utils.statsbomb import StatsBombMatchRow

logger = logging.getLogger(__name__)


class MatchService:
    def __init__(self, repo: MatchRepository) -> None:
        self.repo = repo

    def list_matches(
        self,
        skip: int = 0,
        limit: int = 100,
        competition_id: uuid.UUID | None = None,
        has_events: bool = False,
    ) -> tuple[list[SoccerMatch], int]:
        return self.repo.list_all(
            skip=skip, limit=limit, competition_id=competition_id, has_events=has_events
        )

    def ingest(self, competitions: list[Competition]) -> int:
        from statsbombpy import sb  # type: ignore[import-untyped]

        existing = self.repo.get_existing_statsbomb_ids()
        imported = 0

        for competition in competitions:
            try:
                matches_df = sb.matches(
                    competition_id=competition.statsbomb_id,
                    season_id=competition.season_id,
                )
            except Exception:
                logger.warning(
                    "Could not fetch matches: competition_id=%s season_id=%s",
                    competition.statsbomb_id,
                    competition.season_id,
                )
                continue

            for _, mrow in matches_df.iterrows():
                match_row = StatsBombMatchRow.model_validate(mrow.to_dict())
                if match_row.match_id in existing:
                    continue

                match = SoccerMatch(
                    statsbomb_id=match_row.match_id,
                    competition_id=competition.id,
                    match_date=match_row.match_date[:20],
                    kick_off=match_row.kick_off[:20] if match_row.kick_off else None,
                    home_team=match_row.home_team,
                    away_team=match_row.away_team,
                    home_score=match_row.home_score,
                    away_score=match_row.away_score,
                    stadium=match_row.stadium,
                    referee=match_row.referee,
                    match_week=match_row.match_week,
                    competition_stage_name=match_row.competition_stage,
                    home_team_gender=match_row.home_team_gender,
                    away_team_gender=match_row.away_team_gender,
                    home_team_country_name=match_row.home_team_country_name,
                    away_team_country_name=match_row.away_team_country_name,
                    home_team_group=match_row.home_team_group,
                    away_team_group=match_row.away_team_group,
                    home_manager_name=match_row.home_manager_name,
                    away_manager_name=match_row.away_manager_name,
                    match_status=match_row.match_status,
                    last_updated=match_row.last_updated,
                    match_status_360=match_row.match_status_360,
                )
                self.repo.add(match)
                existing.add(match_row.match_id)
                imported += 1

        logger.info("Match ingest: %d new", imported)
        return imported
