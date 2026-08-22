import uuid

from sqlmodel import Session, select

from app.models.stadium import Stadium


class StadiumRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_external(
        self, source_id: uuid.UUID, external_id: str
    ) -> Stadium | None:
        return self.session.exec(
            select(Stadium).where(
                Stadium.source_id == source_id, Stadium.external_id == external_id
            )
        ).first()

    def list_by_source(self, source_id: uuid.UUID) -> list[Stadium]:
        return list(
            self.session.exec(
                select(Stadium).where(Stadium.source_id == source_id)
            ).all()
        )

    def add(self, stadium: Stadium) -> None:
        self.session.add(stadium)
