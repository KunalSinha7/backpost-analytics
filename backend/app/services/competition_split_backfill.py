import logging
from dataclasses import dataclass

from sqlmodel import Session, func, select

from app.models.competition import CompetitionSeason
from app.services.identity_backfill import EmptyBackfillInputError
from app.services.resolver import EntityResolver

logger = logging.getLogger(__name__)


@dataclass
class SplitBackfillReport:
    competitions_created: int = 0
    seasons_created: int = 0
    editions_linked: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "competitions_created": self.competitions_created,
            "seasons_created": self.seasons_created,
            "editions_linked": self.editions_linked,
        }


class CompetitionSplitBackfillService:
    """Populates `competition` and `season` from the existing edition rows.

    Purely in-database: every value already lives on `competition_season`,
    which is why the migration's pre-flight assertions matter — they are what
    guarantee the 80 edition rows collapse to 24 competitions and 48 seasons
    without having to choose between conflicting values.

    Idempotent: only rows whose FK is still NULL are touched.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.resolver = EntityResolver(session)

    def assert_inputs_present(self) -> None:
        editions = self.session.exec(
            select(func.count()).select_from(CompetitionSeason)
        ).one()
        if editions == 0:
            raise EmptyBackfillInputError(
                "Refusing to backfill: competition_season is empty, so there is "
                "nothing to split. If the test suite just ran against this "
                "database the soccer data was deleted (§7.1a); re-ingest first."
            )

    def run(self) -> SplitBackfillReport:
        self.assert_inputs_present()
        report = SplitBackfillReport()

        before_comps = self._count("competition")
        before_seasons = self._count("season")

        editions = self.session.exec(
            select(CompetitionSeason).where(
                (CompetitionSeason.competition_id == None)  # noqa: E711
                | (CompetitionSeason.season_ref_id == None)  # noqa: E711
            )
        ).all()

        for edition in editions:
            competition = self.resolver.resolve_competition(
                edition.statsbomb_id,
                edition.competition_name,
                country_name=edition.country_name,
                gender=edition.competition_gender,
                is_youth=edition.competition_youth,
                is_international=edition.competition_international,
            )
            season = self.resolver.resolve_season(
                edition.season_id, edition.season_name
            )
            if competition is not None:
                edition.competition_id = competition.id
            if season is not None:
                edition.season_ref_id = season.id
            report.editions_linked += 1

        self.session.commit()
        report.competitions_created = self._count("competition") - before_comps
        report.seasons_created = self._count("season") - before_seasons
        logger.info("Competition split backfill: %s", report.as_dict())
        return report

    def _count(self, table: str) -> int:
        from sqlalchemy import text

        return self.session.execute(
            text(f"SELECT count(*) FROM {table}")  # noqa: S608 - fixed literals only
        ).scalar_one()
