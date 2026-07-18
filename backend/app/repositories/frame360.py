import uuid

from sqlmodel import Session, func, select

from app.models.frame360 import Frame360


class Frame360Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_existing_event_ids_for_match(self, match_id: uuid.UUID) -> set[str]:
        return set(
            self.session.exec(
                select(Frame360.event_statsbomb_id).where(Frame360.match_id == match_id)
            ).all()
        )

    def list_by_match(
        self, match_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> tuple[list[Frame360], int]:
        count = self.session.exec(
            select(func.count())
            .select_from(Frame360)
            .where(Frame360.match_id == match_id)
        ).one()
        frames = self.session.exec(
            select(Frame360)
            .where(Frame360.match_id == match_id)
            .offset(skip)
            .limit(limit)
        ).all()
        return list(frames), count

    def add_batch(self, frames: list[Frame360]) -> None:
        for frame in frames:
            self.session.add(frame)
