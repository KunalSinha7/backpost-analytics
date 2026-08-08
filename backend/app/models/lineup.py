import uuid

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class LineupBase(SQLModel):
    match_id: uuid.UUID = Field(foreign_key="soccer_match.id", index=True)
    team_name: str = Field(max_length=255)
    statsbomb_player_id: int
    player_name: str = Field(max_length=255)
    player_nickname: str | None = Field(default=None, max_length=255)
    jersey_number: int
    country_name: str | None = Field(default=None, max_length=100)
    started: bool = Field(default=False)


class Lineup(LineupBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Declared here and not on LineupBase so it stays out of LineupPublic —
    # same placement as Event.raw_event. SQL NULL means "ingested before this
    # column existed", as distinct from a captured-but-empty payload.
    #
    # none_as_null is what makes that distinction real: without it SQLAlchemy
    # writes Python None as the JSON `null` literal, which is IS NOT NULL in
    # SQL, so "never captured" becomes indistinguishable from "captured null".
    raw: dict | None = Field(
        default=None, sa_column=Column(JSONB(none_as_null=True), nullable=True)
    )


class LineupPublic(LineupBase):
    id: uuid.UUID


class LineupsPublic(SQLModel):
    data: list[LineupPublic]
    count: int
