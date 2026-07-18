import uuid

from sqlalchemy import JSON
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
    duration: float | None = None
    under_pressure: bool | None = None
    off_camera: bool | None = None
    out: bool | None = None


class Event(EventBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    raw_event: dict = Field(default_factory=dict, sa_type=JSON)


class EventPublic(EventBase):
    id: uuid.UUID


class EventsPublic(SQLModel):
    data: list[EventPublic]
    count: int
