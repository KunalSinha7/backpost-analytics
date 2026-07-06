import uuid

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


class LineupPublic(LineupBase):
    id: uuid.UUID


class LineupsPublic(SQLModel):
    data: list[LineupPublic]
    count: int
