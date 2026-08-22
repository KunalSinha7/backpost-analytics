import uuid

from sqlmodel import Field, SQLModel


class MatchFormation(SQLModel, table=True):
    """A team's formation as set by one Starting XI or Tactical Shift event.

    One row per event: a team gets one `MatchFormation` from its Starting XI
    event, plus one more for every Tactical Shift during the match.
    `from_period`/`from_time` mirror the setting event's own `period` and
    `timestamp` columns — the source carries no separate clock for the
    formation itself, only "the event where it changed".
    """

    __tablename__ = "match_formation"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    match_id: uuid.UUID = Field(foreign_key="soccer_match.id", index=True)
    team_id: uuid.UUID = Field(foreign_key="team.id", index=True)
    # Unique: a Starting XI / Tactical Shift event sets exactly one formation
    # snapshot, so this is a 1:1 relationship with the event that set it.
    event_id: uuid.UUID = Field(foreign_key="event.id", unique=True)
    formation: str = Field(max_length=20)
    from_period: int
    from_time: str | None = Field(default=None, max_length=20)


class MatchFormationSlot(SQLModel, table=True):
    """One player's assigned position within a `MatchFormation`.

    Source data (`tactics.lineup`) always carries exactly 11 slots per
    formation. `player_id` and `position_id` are nullable rather than
    required: a slot whose player or position id fails to resolve against the
    `player`/`position` tables is still written, so one bad id cannot cost the
    other ten slots or the formation row itself (see the migration's backfill
    notes).
    """

    __tablename__ = "match_formation_slot"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    match_formation_id: uuid.UUID = Field(
        foreign_key="match_formation.id", index=True
    )
    player_id: uuid.UUID | None = Field(
        default=None, foreign_key="player.id", index=True
    )
    position_id: uuid.UUID | None = Field(
        default=None, foreign_key="position.id", index=True
    )
    jersey_number: int | None = None
