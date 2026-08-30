import uuid
from typing import Any

from sqlalchemy import text
from sqlmodel import Session, col, func, select

from app.models.event import Event
from app.models.player import Player
from app.models.team import Team, TeamAlias

# Assist attribution (issue #31): both columns point at another event in the
# same match, sourced from `raw_event`. Guarded on IS NULL so re-running an
# ingest fills gaps rather than rewriting rows that are already linked.
_LINK_KEY_PASS_SQL = """
    UPDATE event e
    SET key_pass_event_id = kp.id
    FROM event kp
    WHERE e.match_id = :match_id
      AND e.key_pass_event_id IS NULL
      AND e.raw_event ->> 'shot_key_pass_id' IS NOT NULL
      AND kp.statsbomb_id = e.raw_event ->> 'shot_key_pass_id'
"""

_LINK_ASSISTED_SHOT_SQL = """
    UPDATE event e
    SET assisted_shot_event_id = asis.id
    FROM event asis
    WHERE e.match_id = :match_id
      AND e.assisted_shot_event_id IS NULL
      AND e.raw_event ->> 'pass_assisted_shot_id' IS NOT NULL
      AND asis.statsbomb_id = e.raw_event ->> 'pass_assisted_shot_id'
"""


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _team_ids_for_name(self, name: str) -> list[uuid.UUID]:
        """Every team id a display name could refer to, canonical or alias.

        Callers filter by a name chosen from a dropdown, which may be spelled
        the way any one feed spells it. Going through `team_alias` means any
        known spelling finds the team.
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
            # An unresolvable name yields `in_([])`, which matches nothing.
            both(col(Event.team_id).in_(self._team_ids_for_name(team)))
        if period is not None:
            both(Event.period == period)
        if player is not None:
            both(col(Event.player_id).in_(self._player_ids_for_name(player)))
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

        Two queries rather than ORM relationships: events are fetched in
        batches of up to 10,000, and four relationship traversals per row would
        mean tens of thousands of lazy loads for a single response.
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

    def link_assist_events_for_match(self, match_id: uuid.UUID) -> None:
        """Resolve `key_pass_event_id` / `assisted_shot_event_id` for one match.

        Both reference another event in the same match, so every event must be
        committed before this runs. Idempotent.
        """
        self.session.execute(text(_LINK_KEY_PASS_SQL), {"match_id": match_id})
        self.session.execute(text(_LINK_ASSISTED_SHOT_SQL), {"match_id": match_id})

    def add_batch(self, events: list[Event]) -> None:
        self.session.add_all(events)
