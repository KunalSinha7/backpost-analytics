import uuid

from sqlmodel import Field, SQLModel


class PlayerBase(SQLModel):
    statsbomb_id: int = Field(unique=True, index=True)
    name: str = Field(max_length=255, index=True)
    nickname: str | None = Field(default=None, max_length=255)
    nationality: str | None = Field(default=None, max_length=100)


class Player(PlayerBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)


class PlayerPublic(PlayerBase):
    id: uuid.UUID
    match_count: int = 0


class PlayersPublic(SQLModel):
    data: list[PlayerPublic]
    count: int
