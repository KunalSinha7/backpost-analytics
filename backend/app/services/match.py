import logging
import uuid

from sqlmodel import Session

from app.models.competition import CompetitionSeason
from app.models.match import SoccerMatch
from app.repositories.match import MatchRepository
from app.services.resolver import EntityResolver
from app.utils.statsbomb import StatsBombMatchRow

logger = logging.getLogger(__name__)


class MatchService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = MatchRepository(session)
        self.resolver = EntityResolver(session)

    def list_matches(
        self,
        skip: int = 0,
        limit: int = 100,
        competition_season_id: uuid.UUID | None = None,
        has_events: bool = False,
        team_name: str | None = None,
        team_id: uuid.UUID | None = None,
    ) -> tuple[list[tuple[SoccerMatch, str, str]], int, set[uuid.UUID]]:
        return self.repo.list_all(
            skip=skip,
            limit=limit,
            competition_season_id=competition_season_id,
            has_events=has_events,
            team_name=team_name,
            team_id=team_id,
        )

    def list_teams(
        self,
        competition_season_id: uuid.UUID | None = None,
        has_events: bool = False,
    ) -> list[str]:
        return self.repo.list_distinct_teams(
            competition_season_id=competition_season_id, has_events=has_events
        )

    def ingest(self, competitions: list[CompetitionSeason]) -> int:
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

                # One dump feeds both the team lookups below and the `raw`
                # column, so the two cannot disagree.
                payload = match_row.model_dump()
                home = self.resolver.resolve_team(
                    payload.get("home_team_id"),
                    match_row.home_team,
                    authoritative_name=True,
                    gender=match_row.home_team_gender,
                    country_name=match_row.home_team_country_name,
                )
                away = self.resolver.resolve_team(
                    payload.get("away_team_id"),
                    match_row.away_team,
                    authoritative_name=True,
                    gender=match_row.away_team_gender,
                    country_name=match_row.away_team_country_name,
                )
                if home is None or away is None:
                    logger.warning(
                        "Skipping match %s: unresolved team ids", match_row.match_id
                    )
                    continue

                match = SoccerMatch(
                    statsbomb_id=match_row.match_id,
                    home_team_id=home.id,
                    away_team_id=away.id,
                    competition_season_id=competition.id,
                    match_date=match_row.match_date[:20],
                    kick_off=match_row.kick_off[:20] if match_row.kick_off else None,
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
                    # Keeps the source ids the typed fields above discard
                    # (referee, stadium, managers, competition stage).
                    raw=payload,
                )
                self.repo.add(match)
                existing.add(match_row.match_id)
                imported += 1

        logger.info("Match ingest: %d new", imported)
        return imported

    def backfill_raw(self, competitions: list[CompetitionSeason]) -> int:
        """Populate `raw` on matches ingested before that column existed.

        `ingest` only inserts — it skips match ids it already has — so it will
        never fill this in on an existing row. Idempotent: rows that already
        have a payload are left alone, so a partial run can be repeated.
        """
        from statsbombpy import sb  # type: ignore[import-untyped]

        updated = 0
        for competition in competitions:
            existing = {
                m.statsbomb_id: m
                for m in self.repo.list_for_competition(
                    competition.statsbomb_id, competition.season_id
                )
            }
            if not existing or all(m.raw is not None for m in existing.values()):
                continue

            try:
                matches_df = sb.matches(
                    competition_id=competition.statsbomb_id,
                    season_id=competition.season_id,
                )
            except Exception:
                logger.warning(
                    "Could not fetch matches for raw backfill: "
                    "competition_id=%s season_id=%s",
                    competition.statsbomb_id,
                    competition.season_id,
                )
                continue

            for _, mrow in matches_df.iterrows():
                match_row = StatsBombMatchRow.model_validate(mrow.to_dict())
                match = existing.get(match_row.match_id)
                if match is None or match.raw is not None:
                    continue
                match.raw = match_row.model_dump()
                updated += 1

            # Commit per competition to keep transactions bounded.
            self.session.commit()

        logger.info("Match raw backfill: %d rows populated", updated)
        return updated
