import uuid

from sqlmodel import Session, col, select

from app.models.team import Team, TeamAlias


class TeamRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_external(self, source_id: uuid.UUID, external_id: str) -> Team | None:
        return self.session.exec(
            select(Team).where(
                Team.source_id == source_id, Team.external_id == external_id
            )
        ).first()

    def list_by_source(self, source_id: uuid.UUID) -> list[Team]:
        return list(
            self.session.exec(select(Team).where(Team.source_id == source_id)).all()
        )

    def add(self, team: Team) -> None:
        self.session.add(team)

    def has_alias(self, team_id: uuid.UUID, source_id: uuid.UUID, name: str) -> bool:
        return (
            self.session.exec(
                select(TeamAlias.id).where(
                    TeamAlias.team_id == team_id,
                    TeamAlias.source_id == source_id,
                    TeamAlias.name == name,
                )
            ).first()
            is not None
        )

    def add_alias(self, alias: TeamAlias) -> None:
        self.session.add(alias)

    def list_aliases_for(self, team_id: uuid.UUID) -> list[TeamAlias]:
        return list(
            self.session.exec(
                select(TeamAlias)
                .where(TeamAlias.team_id == team_id)
                .order_by(col(TeamAlias.name))
            ).all()
        )
