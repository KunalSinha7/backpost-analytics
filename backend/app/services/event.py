import logging
import uuid

from sqlmodel import Session

from app.exceptions.event import StatsBombFetchError
from app.models.event import Event
from app.repositories.event import EventRepository
from app.repositories.match import MatchRepository
from app.utils.statsbomb import StatsBombEventRow

logger = logging.getLogger(__name__)

_END_LOCATION_FIELDS = ("pass_end_location", "shot_end_location", "carry_end_location")


def _extract_end_location(
    event_row: StatsBombEventRow,
) -> tuple[float | None, float | None]:
    for field in _END_LOCATION_FIELDS:
        value = getattr(event_row, field, None)
        if value:
            return value[0], value[1]
    return None, None


class EventService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.event_repo = EventRepository(session)
        self.match_repo = MatchRepository(session)

    def list_by_match(
        self,
        match_id: uuid.UUID,
        skip: int = 0,
        limit: int = 10000,
        type_name: str | None = None,
        team: str | None = None,
        period: int | None = None,
        player: str | None = None,
        possession: int | None = None,
        team_id: uuid.UUID | None = None,
    ) -> tuple[list[Event], int, dict[uuid.UUID, str]]:
        return self.event_repo.list_by_match(
            match_id,
            skip=skip,
            limit=limit,
            type_name=type_name,
            team=team,
            period=period,
            player=player,
            possession=possession,
            team_id=team_id,
        )

    def ingest_for_competition(
        self, competition_statsbomb_id: int, season_id: int
    ) -> int:
        """
        Fetches and stores all events for every match in the given competition/season.
        Commits per match to keep transactions bounded.
        Callable outside HTTP context (background task or standalone script).
        Returns count of newly inserted events.
        """
        from statsbombpy import sb  # type: ignore[import-untyped]

        matches = self.match_repo.list_for_competition(
            competition_statsbomb_id, season_id
        )
        existing_ids = self.event_repo.get_existing_statsbomb_ids()
        total_imported = 0

        for match in matches:
            try:
                events_df = sb.events(match_id=match.statsbomb_id)
            except Exception as exc:
                raise StatsBombFetchError(match.statsbomb_id) from exc

            batch: list[Event] = []
            for _, row in events_df.iterrows():  # type: ignore
                event_row = StatsBombEventRow.model_validate(row.to_dict())
                if event_row.id in existing_ids:
                    continue

                end_location_x, end_location_y = _extract_end_location(event_row)
                pass_recipient = getattr(event_row, "pass_recipient", None)
                event = Event(
                    statsbomb_id=event_row.id,
                    match_id=match.id,
                    index=event_row.index,
                    period=event_row.period,
                    timestamp=event_row.timestamp,
                    minute=event_row.minute,
                    second=event_row.second,
                    type_name=event_row.type or "",
                    possession=event_row.possession,
                    play_pattern_name=event_row.play_pattern,
                    location_x=event_row.location[0] if event_row.location else None,
                    location_y=event_row.location[1] if event_row.location else None,
                    end_location_x=end_location_x,
                    end_location_y=end_location_y,
                    duration=event_row.duration,
                    under_pressure=event_row.under_pressure,
                    off_camera=event_row.off_camera,
                    out=event_row.out,
                    raw_event=event_row.model_dump(),
                )
                batch.append(event)
                existing_ids.add(event_row.id)

            self.event_repo.add_batch(batch)
            self.session.commit()
            total_imported += len(batch)
            logger.info(
                "Events ingested: match_id=%s, new=%d", match.statsbomb_id, len(batch)
            )

        return total_imported
