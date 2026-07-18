import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import SQLModel

from app.api.deps import SessionDep, SuperuserDep
from app.exceptions.competition import CompetitionNotFoundError
from app.models.competition import CompetitionPublic, CompetitionsPublic
from app.repositories.competition import CompetitionRepository
from app.repositories.match import MatchRepository
from app.services.competition import CompetitionService
from app.services.match import MatchService

router = APIRouter(prefix="/competitions", tags=["soccer"])
logger = logging.getLogger(__name__)


class IngestResult(SQLModel):
    imported_competitions: int
    imported_matches: int


@router.get("/", response_model=CompetitionsPublic, operation_id="readCompetitions")
def read_competitions(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    repo = CompetitionRepository(session)
    rows, count = repo.list_all(skip=skip, limit=limit)
    return CompetitionsPublic(
        data=[CompetitionPublic.model_validate(r) for r in rows],
        count=count,
    )


@router.post("/ingest", response_model=IngestResult, operation_id="ingestSoccerData")
def ingest_soccer_data(session: SessionDep, _current_user: SuperuserDep) -> Any:
    comp_repo = CompetitionRepository(session)
    match_repo = MatchRepository(session)
    try:
        n_comps, competitions = CompetitionService(comp_repo).ingest()
        n_matches = MatchService(match_repo).ingest(competitions)
        session.commit()
    except CompetitionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return IngestResult(imported_competitions=n_comps, imported_matches=n_matches)


class StatsBombCompetition(SQLModel):
    competition_id: int
    competition_name: str
    country_name: str
    season_id: int
    season_name: str
    has_360: bool


@router.get(
    "/available",
    response_model=list[StatsBombCompetition],
    operation_id="getAvailableCompetitions",
)
def get_available_competitions() -> list[StatsBombCompetition]:
    """Returns the full StatsBomb open data competition catalog."""
    import math
    import warnings

    from statsbombpy import sb  # type: ignore[import-untyped]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = sb.competitions()

    result = []
    for _, row in df.iterrows():
        val = row.get("match_available_360")
        has_360 = (
            val is not None
            and not (isinstance(val, float) and math.isnan(val))
            and str(val) not in ("", "nan", "None")
        )
        result.append(
            StatsBombCompetition(
                competition_id=int(row["competition_id"]),
                competition_name=str(row["competition_name"]),
                country_name=str(row["country_name"]),
                season_id=int(row["season_id"]),
                season_name=str(row["season_name"]),
                has_360=bool(has_360),
            )
        )

    return sorted(result, key=lambda x: (x.competition_name, x.season_name))
