import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks
from sqlmodel import Session

from app.api.deps import SessionDep, SuperuserDep
from app.exceptions.event import StatsBombFetchError
from app.models.event import EventPublic, EventsPublic
from app.services.event import EventService
from app.services.frame360 import Frame360Service
from app.services.lineup import LineupService

router = APIRouter(prefix="/events", tags=["soccer"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=EventsPublic, operation_id="readEvents")
def read_events(
    session: SessionDep,
    match_id: uuid.UUID,
    skip: int = 0,
    limit: int = 10000,
    type_name: str | None = None,
    team: str | None = None,
    period: int | None = None,
) -> Any:
    events, count = EventService(session).list_by_match(
        match_id,
        skip=skip,
        limit=limit,
        type_name=type_name,
        team=team,
        period=period,
    )
    return EventsPublic(
        data=[EventPublic.model_validate(e) for e in events],
        count=count,
    )


@router.post("/ingest", status_code=202, operation_id="ingestEvents")
def ingest_events(
    background_tasks: BackgroundTasks,
    _current_user: SuperuserDep,
    competition_statsbomb_id: int = 43,
    season_id: int = 3,
) -> dict[str, str]:
    background_tasks.add_task(_run_ingest, competition_statsbomb_id, season_id)
    return {
        "message": (
            f"Event ingestion started for competition {competition_statsbomb_id}"
            f" / season {season_id}"
        )
    }


def _run_ingest(competition_statsbomb_id: int, season_id: int) -> None:
    from app.core.db import engine

    with Session(engine) as session:
        try:
            n_events = EventService(session).ingest_for_competition(
                competition_statsbomb_id, season_id
            )
            logger.info("Background ingest complete: %d events", n_events)
        except StatsBombFetchError as e:
            logger.error("Background event ingest failed: %s", e)

        n_lineups = LineupService(session).ingest_for_competition(
            competition_statsbomb_id, season_id
        )
        logger.info("Background lineup ingest complete: %d players", n_lineups)

        n_frames = Frame360Service(session).ingest_for_competition(
            competition_statsbomb_id, season_id
        )
        logger.info("Background 360 ingest complete: %d frames", n_frames)
