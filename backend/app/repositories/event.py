import uuid
from typing import Any

from sqlmodel import Session, col, func, select

from app.models.event import Event
from app.models.player import Player
from app.models.team import Team, TeamAlias


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _team_ids_for_name(self, name: str) -> list[uuid.UUID]:
        """Every team id a display name could refer to, canonical or alias.

        This is the Marseille bug (§1.2) at its point of failure. `/matches/teams`
        populates the dropdown from one feed's spelling while events were stored
        under another, so a string comparison between them matched nothing and
        the UI showed an empty pitch for a team with thousands of events.

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

    def _player_ids_for_name(self, name: str) -> list[uuid.UUID]:
        return list(
            self.session.exec(select(Player.id).where(Player.name == name)).all()
        )

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
    ) -> tuple[list[Event], int, dict[uuid.UUID, str]]:
        count_stmt = (
            select(func.count()).select_from(Event).where(Event.match_id == match_id)
        )
        stmt = select(Event).where(Event.match_id == match_id)

        def both(clause: Any) -> None:
            nonlocal stmt, count_stmt
            stmt = stmt.where(clause)
            count_stmt = count_stmt.where(clause)

        if type_name is not None:
            both(Event.type_name == type_name)
        if team_id is not None:
            both(Event.team_id == team_id)
        if team is not None:
            resolved = self._team_ids_for_name(team)
            both(
                col(Event.team_id).in_(resolved)
                if resolved
                else col(Event.team_id).in_([])
            )
        if period is not None:
            both(Event.period == period)
        if player is not None:
            resolved_players = self._player_ids_for_name(player)
            both(
                col(Event.player_id).in_(resolved_players)
                if resolved_players
                else col(Event.player_id).in_([])
            )
        if possession is not None:
            both(Event.possession == possession)

        count = self.session.exec(count_stmt).one()
        events = list(
            self.session.exec(
                stmt.order_by(col(Event.index)).offset(skip).limit(limit)
            ).all()
        )
        return events, count, self._name_map(events)

    def _name_map(self, events: list[Event]) -> dict[uuid.UUID, str]:
        """One id -> name lookup covering every entity the page references.

        Deliberately two queries rather than ORM relationships: `read_events`
        defaults to `limit=10000`, and four relationship traversals per row
        would be up to 40,000 lazy loads for one response (§6). Scoped to a
        single match, this is at most two teams and a few dozen players.
        """
        team_ids = {e.team_id for e in events} | {
            e.possession_team_id for e in events if e.possession_team_id
        }
        player_ids = {e.player_id for e in events if e.player_id} | {
            e.pass_recipient_id for e in events if e.pass_recipient_id
        }

        names: dict[uuid.UUID, str] = {}
        if team_ids:
            for tid, name in self.session.exec(
                select(Team.id, Team.name).where(col(Team.id).in_(team_ids))
            ).all():
                names[tid] = name
        if player_ids:
            for pid, name in self.session.exec(
                select(Player.id, Player.name).where(col(Player.id).in_(player_ids))
            ).all():
                names[pid] = name
        return names

    def get_existing_statsbomb_ids(self) -> set[str]:
        return set(self.session.exec(select(Event.statsbomb_id)).all())

    def add_batch(self, events: list[Event]) -> None:
        self.session.add_all(events)
