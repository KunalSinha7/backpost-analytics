import logging

from app.models.competition import Competition
from app.repositories.competition import CompetitionRepository
from app.utils.statsbomb import StatsBombCompetitionRow

logger = logging.getLogger(__name__)


class CompetitionService:
    def __init__(self, repo: CompetitionRepository) -> None:
        self.repo = repo

    def ingest(self) -> tuple[int, list[Competition]]:
        from statsbombpy import sb  # type: ignore[import-untyped]

        existing = self.repo.get_existing_keys()
        imported = 0
        all_competitions: list[Competition] = []

        for _, row in sb.competitions().iterrows():
            comp_row = StatsBombCompetitionRow.model_validate(row.to_dict())
            cid, sid = comp_row.competition_id, comp_row.season_id

            if (cid, sid) not in existing:
                comp = Competition(
                    statsbomb_id=cid,
                    season_id=sid,
                    country_name=comp_row.country_name,
                    competition_name=comp_row.competition_name,
                    competition_gender=comp_row.competition_gender,
                    competition_youth=comp_row.competition_youth,
                    competition_international=comp_row.competition_international,
                    season_name=comp_row.season_name,
                    match_updated=comp_row.match_updated,
                    match_available=comp_row.match_available,
                    match_updated_360=comp_row.match_updated_360,
                    match_available_360=comp_row.match_available_360,
                )
                self.repo.add(comp)
                existing.add((cid, sid))
                imported += 1
                all_competitions.append(comp)
            else:
                all_competitions.append(self.repo.get_by_statsbomb_key(cid, sid))

        logger.info("Competition ingest: %d new", imported)
        return imported, all_competitions
