import logging

from sqlmodel import Session

from app.models.competition import CompetitionSeason
from app.repositories.competition import CompetitionRepository
from app.services.resolver import EntityResolver
from app.utils.statsbomb import StatsBombCompetitionRow

logger = logging.getLogger(__name__)


class CompetitionService:
    def __init__(self, session: Session) -> None:
        self.repo = CompetitionRepository(session)
        self.resolver = EntityResolver(session)

    def list_competitions(
        self,
        skip: int = 0,
        limit: int = 100,
        has_matches: bool = False,
        has_events: bool = False,
    ) -> tuple[list[tuple[CompetitionSeason, int]], int]:
        return self.repo.list_all(
            skip=skip, limit=limit, has_matches=has_matches, has_events=has_events
        )

    def ingest(self) -> tuple[int, list[CompetitionSeason]]:
        from statsbombpy import sb  # type: ignore[import-untyped]

        existing = self.repo.get_existing_keys()
        imported = 0
        all_competitions: list[CompetitionSeason] = []

        for _, row in sb.competitions().iterrows():
            comp_row = StatsBombCompetitionRow.model_validate(row.to_dict())
            cid, sid = comp_row.competition_id, comp_row.season_id

            if (cid, sid) not in existing:
                comp = CompetitionSeason(
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
                    raw=comp_row.model_dump(),
                )
                # Resolved at ingest, not left to the backfill. A backfill is
                # one-shot; if ingest does not populate the FKs then every
                # newly ingested edition arrives unlinked and the split decays
                # from the first import onward (§6/M1).
                competition = self.resolver.resolve_competition(
                    cid,
                    comp_row.competition_name,
                    country_name=comp_row.country_name,
                    gender=comp_row.competition_gender,
                    is_youth=comp_row.competition_youth,
                    is_international=comp_row.competition_international,
                )
                season = self.resolver.resolve_season(sid, comp_row.season_name)
                comp.competition_id = competition.id if competition else None
                comp.season_ref_id = season.id if season else None
                self.repo.add(comp)
                existing.add((cid, sid))
                imported += 1
                all_competitions.append(comp)
            else:
                all_competitions.append(self.repo.get_by_statsbomb_key(cid, sid))

        logger.info("Competition ingest: %d new", imported)
        return imported, all_competitions
