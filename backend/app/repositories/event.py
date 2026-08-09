import uuid

from sqlmodel import Session, col, func, or_, select

from app.models.event import Event
from app.models.team import Team, TeamAlias


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _team_ids_for_name(self, name: str) -> list[uuid.UUID]:
        """Every team id a display name could refer to, canonical or alias.

        This is the Marseille bug (§1.2) at its point of failure. `/matches/teams`
        populates the dropdown from the *match* feed ("Olympique de Marseille")
        while `event.team` holds the *event* feed's spelling ("Marseille"), so a
        string comparison between them matches nothing and the UI shows zero
        events for a team that has 1,920 of them.

        Looking the name up through `team_alias` is what closes the gap without
        the caller — or the frontend — changing anything.
        """
        ids = set(self.session.exec(select(Team.id).where(Team.name == name)).all())
        ids |= set(
            self.session.exec(
                select(TeamAlias.team_id).where(TeamAlias.name == name)
            ).all()
        )
        return list(ids)

    def list_by_match(
        self,
        match_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        type_name: str | None = None,
        team: str | None = None,
        period: int | None = None,
        player: str | None = None,
        possession: int | None = None,
        team_id: uuid.UUID | None = None,
    ) -> tuple[list[Event], int]:
        count_stmt = (
            select(func.count()).select_from(Event).where(Event.match_id == match_id)
        )
        stmt = select(Event).where(Event.match_id == match_id)
        if type_name is not None:
            count_stmt = count_stmt.where(Event.type_name == type_name)
            stmt = stmt.where(Event.type_name == type_name)
        if team_id is not None:
            count_stmt = count_stmt.where(Event.team_id == team_id)
            stmt = stmt.where(Event.team_id == team_id)
        if team is not None:
            resolved = self._team_ids_for_name(team)
            if resolved:
                # OR rather than a straight swap: events ingested before the
                # backfill still have a NULL team_id, and dropping the string
                # comparison would make them vanish from filtered results. The
                # two clauses select the same rows for every team whose feeds
                # agree, so the only responses that change are the ones that
                # were already wrong.
                team_clause = or_(col(Event.team_id).in_(resolved), Event.team == team)
            else:
                team_clause = Event.team == team  # type: ignore[assignment]
            count_stmt = count_stmt.where(team_clause)
            stmt = stmt.where(team_clause)
        if period is not None:
            count_stmt = count_stmt.where(Event.period == period)
            stmt = stmt.where(Event.period == period)
        if player is not None:
            count_stmt = count_stmt.where(Event.player == player)
            stmt = stmt.where(Event.player == player)
        if possession is not None:
            count_stmt = count_stmt.where(Event.possession == possession)
            stmt = stmt.where(Event.possession == possession)
        count = self.session.exec(count_stmt).one()
        events = self.session.exec(
            stmt.order_by(col(Event.index)).offset(skip).limit(limit)
        ).all()
        return list(events), count

    def get_existing_statsbomb_ids(self) -> set[str]:
        return set(self.session.exec(select(Event.statsbomb_id)).all())

    def add_batch(self, events: list[Event]) -> None:
        self.session.add_all(events)
