import uuid

from sqlmodel import Session, col, func, select

from app.models.event import Event


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_match(
        self, match_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> tuple[list[Event], int]:
        count = self.session.exec(
            select(func.count()).select_from(Event).where(Event.match_id == match_id)
        ).one()
        events = self.session.exec(
            select(Event)
            .where(Event.match_id == match_id)
            .order_by(col(Event.index))
            .offset(skip)
            .limit(limit)
        ).all()
        return list(events), count

    def get_existing_statsbomb_ids(self) -> set[str]:
        return set(self.session.exec(select(Event.statsbomb_id)).all())

    def add_batch(self, events: list[Event]) -> None:
        for event in events:
            self.session.add(event)
