import logging
import uuid

from sqlmodel import Session

from app.models.frame360 import Frame360
from app.repositories.frame360 import Frame360Repository
from app.repositories.match import MatchRepository
from app.utils.statsbomb import StatsBombFrameRow

logger = logging.getLogger(__name__)


class Frame360Service:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.frame_repo = Frame360Repository(session)
        self.match_repo = MatchRepository(session)

    def list_by_match(
        self, match_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> tuple[list[Frame360], int]:
        return self.frame_repo.list_by_match(match_id, skip=skip, limit=limit)

    def ingest_for_competition(
        self, competition_statsbomb_id: int, season_id: int
    ) -> int:
        from statsbombpy import sb  # type: ignore[import-untyped]

        matches = self.match_repo.list_for_competition(
            competition_statsbomb_id, season_id
        )
        total_imported = 0

        for match in matches:
            if match.match_status_360 != "available":
                continue

            existing = self.frame_repo.get_existing_event_ids_for_match(match.id)
            if existing:
                continue

            try:
                # fmt="dict", not the default DataFrame. statsbombpy 1.19.0's
                # frame flattening raises under pandas 3.x —
                #   InvalidIndexError: Reindexing only valid with uniquely
                #   valued Index objects
                # — for every match, so the DataFrame path ingested exactly
                # zero frames while reporting success. The dict path returns
                # the same payload and is unaffected.
                frames = sb.frames(match_id=match.statsbomb_id, fmt="dict")
            except Exception:
                # Warning, not debug: this is a fetch failure, and at debug it
                # was invisible — which is how the pandas breakage above went
                # unnoticed behind a cheerful "0 frames" result.
                logger.warning(
                    "Could not fetch 360 frames for match %s", match.statsbomb_id
                )
                continue

            event_ids = self.frame_repo.event_ids_by_statsbomb_id(match.id)

            batch: list[Frame360] = []
            for entry in frames:
                # The dict payload names it `event_uuid`; the DataFrame path
                # called the same field `id`.
                frame_row = StatsBombFrameRow.model_validate(
                    {**entry, "id": entry.get("event_uuid", "")}
                )
                if not frame_row.id or frame_row.id in existing:
                    continue
                frame = Frame360(
                    match_id=match.id,
                    event_statsbomb_id=frame_row.id,
                    # Resolved here rather than left to a backfill: events are
                    # ingested before frames, so the event already exists.
                    event_id=event_ids.get(frame_row.id),
                    visible_area=frame_row.visible_area or [],
                    freeze_frame=frame_row.freeze_frame or [],
                )
                batch.append(frame)
                existing.add(frame_row.id)

            if batch:
                self.frame_repo.add_batch(batch)
                self.session.commit()
                total_imported += len(batch)
                logger.info(
                    "360 frames ingested: match_id=%s, frames=%d",
                    match.statsbomb_id,
                    len(batch),
                )

        return total_imported
