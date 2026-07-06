import uuid

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel


class Frame360Base(SQLModel):
    match_id: uuid.UUID = Field(foreign_key="soccer_match.id", index=True)
    event_statsbomb_id: str = Field(max_length=36, index=True)
    visible_area: list = Field(default_factory=list, sa_type=JSON)
    freeze_frame: list = Field(default_factory=list, sa_type=JSON)


class Frame360(Frame360Base, table=True):
    __tablename__ = "frame360"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class Frame360Public(Frame360Base):
    id: uuid.UUID


class Frames360Public(SQLModel):
    data: list[Frame360Public]
    count: int
