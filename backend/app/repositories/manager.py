import uuid

from sqlmodel import Session, select

from app.models.manager import Manager


class ManagerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_external(
        self, source_id: uuid.UUID, external_id: str
    ) -> Manager | None:
        return self.session.exec(
            select(Manager).where(
                Manager.source_id == source_id, Manager.external_id == external_id
            )
        ).first()

    def list_by_source(self, source_id: uuid.UUID) -> list[Manager]:
        return list(
            self.session.exec(
                select(Manager).where(Manager.source_id == source_id)
            ).all()
        )

    def add(self, manager: Manager) -> None:
        self.session.add(manager)
