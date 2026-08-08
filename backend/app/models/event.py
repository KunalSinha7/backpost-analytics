import uuid

from sqlalchemy import JSON, Index
from sqlmodel import Field, SQLModel


class EventBase(SQLModel):
    statsbomb_id: str = Field(max_length=36, index=True, unique=True)
    match_id: uuid.UUID = Field(foreign_key="soccer_match.id")
    index: int
    period: int
    timestamp: str | None = Field(default=None, max_length=20)
    minute: int
    second: int
    type_name: str = Field(max_length=100)
    possession: int | None = None
    possession_team_name: str | None = Field(default=None, max_length=255)
    play_pattern_name: str | None = Field(default=None, max_length=100)
    team: str = Field(max_length=255)
    player: str | None = Field(default=None, max_length=255)
    location_x: float | None = None
    location_y: float | None = None
    end_location_x: float | None = None
    end_location_y: float | None = None
    pass_recipient: str | None = Field(default=None, max_length=255)
    duration: float | None = None
    under_pressure: bool | None = None
    off_camera: bool | None = None
    out: bool | None = None


class Event(EventBase, table=True):
    # Composite rather than a plain index=True on match_id: every read of this
    # table is "the events of one match, in index order", so the second column
    # serves the ORDER BY as well as the lookup. A leading-column-only index
    # would be redundant with this one.
    __table_args__ = (Index("ix_event_match_id_index", "match_id", "index"),)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    raw_event: dict = Field(default_factory=dict, sa_type=JSON)
    # All on the table class, not EventBase: EventPublic must not change shape.
    # `team` / `player` / `pass_recipient` keep serving the API unchanged, and
    # the ids below are populated beside them for the season-stats query.
    #
    # Backfilled from raw_event, which covers 100% of rows — no re-fetch. Note
    # the ids arrive as float strings ("7626.0") because pandas widens nullable
    # int columns to float64, so casts must go ::numeric::bigint; a bare ::int
    # throws (§1.5/B1).
    # team_id/player_id are deliberately NOT index=True. §2.2 specifies the
    # composite indexes (player_id, match_id) and (team_id, match_id) for the
    # season-stats query in Phase 3; single-column indexes here would be
    # redundant with those (same leading column) and would have to be dropped
    # again. Same reasoning that made ix_event_match_id_index composite.
    team_id: uuid.UUID | None = Field(default=None, foreign_key="team.id")
    possession_team_id: uuid.UUID | None = Field(default=None, foreign_key="team.id")
    player_id: uuid.UUID | None = Field(default=None, foreign_key="player.id")
    pass_recipient_id: uuid.UUID | None = Field(default=None, foreign_key="player.id")
    position_id: uuid.UUID | None = Field(default=None, foreign_key="position.id")
    substitution_replacement_id: uuid.UUID | None = Field(
        default=None, foreign_key="player.id"
    )


class EventPublic(EventBase):
    id: uuid.UUID


class EventsPublic(SQLModel):
    data: list[EventPublic]
    count: int
