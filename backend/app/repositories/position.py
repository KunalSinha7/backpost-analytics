import uuid

from sqlmodel import Session, select

from app.models.position import Position


class PositionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_external(
        self, source_id: uuid.UUID, external_id: str
    ) -> Position | None:
        return self.session.exec(
            select(Position).where(
                Position.source_id == source_id, Position.external_id == external_id
            )
        ).first()

    def list_by_source(self, source_id: uuid.UUID) -> list[Position]:
        return list(
            self.session.exec(
                select(Position).where(Position.source_id == source_id)
            ).all()
        )

    def add(self, position: Position) -> None:
        self.session.add(position)
