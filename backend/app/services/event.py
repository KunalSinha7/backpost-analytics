import logging

from sqlmodel import Session

from app.exceptions.event import StatsBombFetchError
from app.models.event import Event
from app.repositories.event import EventRepository
from app.repositories.match import MatchRepository
from app.utils.statsbomb import StatsBombEventRow

logger = logging.getLogger(__name__)


class EventService:
    def __init__(
        self, event_repo: EventRepository, match_repo: MatchRepository
    ) -> None:
        self.event_repo = event_repo
        self.match_repo = match_repo

    def ingest_for_competition(
        self, competition_statsbomb_id: int, season_id: int, session: Session
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
                    possession_team_name=event_row.possession_team,
                    play_pattern_name=event_row.play_pattern,
                    team=event_row.team or "",
                    player=event_row.player,
                    location_x=event_row.location[0] if event_row.location else None,
                    location_y=event_row.location[1] if event_row.location else None,
                    duration=event_row.duration,
                    under_pressure=event_row.under_pressure,
                    off_camera=event_row.off_camera,
                    out=event_row.out,
                    raw_event=event_row.model_dump(),
                )
                batch.append(event)
                existing_ids.add(event_row.id)

            self.event_repo.add_batch(batch)
            session.commit()
            total_imported += len(batch)
            logger.info(
                "Events ingested: match_id=%s, new=%d", match.statsbomb_id, len(batch)
            )

        return total_imported
