import uuid

from sqlmodel import Session, select

from app.models.referee import Referee


class RefereeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_external(
        self, source_id: uuid.UUID, external_id: str
    ) -> Referee | None:
        return self.session.exec(
            select(Referee).where(
                Referee.source_id == source_id, Referee.external_id == external_id
            )
        ).first()

    def list_by_source(self, source_id: uuid.UUID) -> list[Referee]:
        return list(
            self.session.exec(
                select(Referee).where(Referee.source_id == source_id)
            ).all()
        )

    def add(self, referee: Referee) -> None:
        self.session.add(referee)
