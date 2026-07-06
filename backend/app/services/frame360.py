import logging

from sqlmodel import Session

from app.models.frame360 import Frame360
from app.repositories.frame360 import Frame360Repository
from app.repositories.match import MatchRepository
from app.utils.statsbomb import StatsBombFrameRow

logger = logging.getLogger(__name__)


class Frame360Service:
    def __init__(self, frame_repo: Frame360Repository, match_repo: MatchRepository) -> None:
        self.frame_repo = frame_repo
        self.match_repo = match_repo

    def ingest_for_competition(
        self, competition_statsbomb_id: int, season_id: int, session: Session
    ) -> int:
        from statsbombpy import sb  # type: ignore[import-untyped]

        matches = self.match_repo.list_for_competition(competition_statsbomb_id, season_id)
        total_imported = 0

        for match in matches:
            if match.match_status_360 != "available":
                continue

            existing = self.frame_repo.get_existing_event_ids_for_match(match.id)
            if existing:
                continue

            try:
                frames_df = sb.frames(match_id=match.statsbomb_id)
            except Exception:
                logger.debug("No 360 frames available for match %s", match.statsbomb_id)
                continue

            batch: list[Frame360] = []
            for _, row in frames_df.iterrows():
                frame_row = StatsBombFrameRow.model_validate(row.to_dict())
                if frame_row.id in existing:
                    continue
                frame = Frame360(
                    match_id=match.id,
                    event_statsbomb_id=frame_row.id,
                    visible_area=frame_row.visible_area or [],
                    freeze_frame=frame_row.freeze_frame or [],
                )
                batch.append(frame)
                existing.add(frame_row.id)

            if batch:
                self.frame_repo.add_batch(batch)
                session.commit()
                total_imported += len(batch)
                logger.info(
                    "360 frames ingested: match_id=%s, frames=%d",
                    match.statsbomb_id,
                    len(batch),
                )

        return total_imported
