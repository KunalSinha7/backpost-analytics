import uuid

from sqlmodel import Session, select

from app.models.competition_stage import CompetitionStage


class CompetitionStageRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_external(
        self, source_id: uuid.UUID, external_id: str
    ) -> CompetitionStage | None:
        return self.session.exec(
            select(CompetitionStage).where(
                CompetitionStage.source_id == source_id,
                CompetitionStage.external_id == external_id,
            )
        ).first()

    def list_by_source(self, source_id: uuid.UUID) -> list[CompetitionStage]:
        return list(
            self.session.exec(
                select(CompetitionStage).where(CompetitionStage.source_id == source_id)
            ).all()
        )

    def add(self, stage: CompetitionStage) -> None:
        self.session.add(stage)
