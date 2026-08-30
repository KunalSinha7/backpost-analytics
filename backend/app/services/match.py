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

                # Deferred entities (issue #30): resolved the same way as team,
                # from the *_id columns the typed fields never declared. A
                # None external_id (e.g. no referee recorded) resolves to
                # None here too, leaving the FK null rather than fabricating
                # an entity.
                referee = self.resolver.resolve_referee(
                    payload.get("referee_id"), match_row.referee
                )
                stadium = self.resolver.resolve_stadium(
                    payload.get("stadium_id"), match_row.stadium
                )
                home_manager = self.resolver.resolve_manager(
                    payload.get("home_manager_id"), match_row.home_manager_name
                )
                away_manager = self.resolver.resolve_manager(
                    payload.get("away_manager_id"), match_row.away_manager_name
                )
                competition_stage = self.resolver.resolve_competition_stage(
                    payload.get("competition_stage_id"), match_row.competition_stage
                )

                match = SoccerMatch(
                    statsbomb_id=match_row.match_id,
                    home_team_id=home.id,
                    away_team_id=away.id,
                    referee_id=referee.id if referee else None,
                    stadium_id=stadium.id if stadium else None,
                    home_manager_id=home_manager.id if home_manager else None,
                    away_manager_id=away_manager.id if away_manager else None,
                    competition_stage_id=(
                        competition_stage.id if competition_stage else None
                    ),
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

    def backfill_deferred_entities(self, competitions: list[CompetitionSeason]) -> int:
        """Backfill referee/stadium/manager/competition_stage FKs via re-fetch.

        These five FKs (issue #30) did not exist when older rows were
        ingested, so `ingest` never set them on those rows — it only sets
        them going forward. This re-fetches `sb.matches()`, the same cheap,
        cached endpoint `ingest` already reads, and resolves each id through
        `EntityResolver` exactly as `ingest` does.

        Never overwrites a value already resolved, so a partial or repeated
        run cannot regress data. It is not a no-op on a second call for a
        competition where a field is genuinely absent in the source (e.g. no
        referee recorded for that match) — "still null" and "not yet
        backfilled" are indistinguishable on a nullable column, so such a
        competition is re-fetched every call. That costs a wasted request,
        never wrong data.
        """
        from statsbombpy import sb  # type: ignore[import-untyped]

        fk_fields = (
            "referee_id",
            "stadium_id",
            "home_manager_id",
            "away_manager_id",
            "competition_stage_id",
        )
        updated = 0
        for competition in competitions:
            existing = {
                m.statsbomb_id: m
                for m in self.repo.list_for_competition(
                    competition.statsbomb_id, competition.season_id
                )
            }
            if not existing or all(
                all(getattr(m, field) is not None for field in fk_fields)
                for m in existing.values()
            ):
                continue

            try:
                matches_df = sb.matches(
                    competition_id=competition.statsbomb_id,
                    season_id=competition.season_id,
                )
            except Exception:
                logger.warning(
                    "Could not fetch matches for deferred-entity backfill: "
                    "competition_id=%s season_id=%s",
                    competition.statsbomb_id,
                    competition.season_id,
                )
                continue

            for _, mrow in matches_df.iterrows():
                match_row = StatsBombMatchRow.model_validate(mrow.to_dict())
                match = existing.get(match_row.match_id)
                if match is None:
                    continue

                payload = match_row.model_dump()
                changed = False

                if match.referee_id is None:
                    referee = self.resolver.resolve_referee(
                        payload.get("referee_id"), match_row.referee
                    )
                    if referee is not None:
                        match.referee_id = referee.id
                        changed = True
                if match.stadium_id is None:
                    stadium = self.resolver.resolve_stadium(
                        payload.get("stadium_id"), match_row.stadium
                    )
                    if stadium is not None:
                        match.stadium_id = stadium.id
                        changed = True
                if match.home_manager_id is None:
                    home_manager = self.resolver.resolve_manager(
                        payload.get("home_manager_id"), match_row.home_manager_name
                    )
                    if home_manager is not None:
                        match.home_manager_id = home_manager.id
                        changed = True
                if match.away_manager_id is None:
                    away_manager = self.resolver.resolve_manager(
                        payload.get("away_manager_id"), match_row.away_manager_name
                    )
                    if away_manager is not None:
                        match.away_manager_id = away_manager.id
                        changed = True
                if match.competition_stage_id is None:
                    stage = self.resolver.resolve_competition_stage(
                        payload.get("competition_stage_id"),
                        match_row.competition_stage,
                    )
                    if stage is not None:
                        match.competition_stage_id = stage.id
                        changed = True

                if changed:
                    updated += 1

            # Commit per competition to keep transactions bounded.
            self.session.commit()

        logger.info("Match deferred-entity backfill: %d rows updated", updated)
        return updated
