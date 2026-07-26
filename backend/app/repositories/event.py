import uuid

from sqlmodel import Session, col, func, select

from app.models.event import Event


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_match(
        self,
        match_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        type_name: str | None = None,
        team: str | None = None,
        period: int | None = None,
    ) -> tuple[list[Event], int]:
        count_stmt = (
            select(func.count()).select_from(Event).where(Event.match_id == match_id)
        )
        stmt = select(Event).where(Event.match_id == match_id)
        if type_name is not None:
            count_stmt = count_stmt.where(Event.type_name == type_name)
            stmt = stmt.where(Event.type_name == type_name)
        if team is not None:
            count_stmt = count_stmt.where(Event.team == team)
            stmt = stmt.where(Event.team == team)
        if period is not None:
            count_stmt = count_stmt.where(Event.period == period)
            stmt = stmt.where(Event.period == period)
        count = self.session.exec(count_stmt).one()
        events = self.session.exec(
            stmt.order_by(col(Event.index)).offset(skip).limit(limit)
        ).all()
        return list(events), count

    def get_existing_statsbomb_ids(self) -> set[str]:
        return set(self.session.exec(select(Event.statsbomb_id)).all())

    def add_batch(self, events: list[Event]) -> None:
        self.session.add_all(events)
