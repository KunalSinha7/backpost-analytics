import uuid

from sqlmodel import Field, SQLModel


class PlayerBase(SQLModel):
    statsbomb_id: int = Field(unique=True, index=True)
    name: str = Field(max_length=255, index=True)
    nickname: str | None = Field(default=None, max_length=255)
    nationality: str | None = Field(default=None, max_length=100)


class Player(PlayerBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Added beside `statsbomb_id`, which stays. Renaming it was cut from the
    # plan (§6/H1): it is in the `required` list of five public schemas and is a
    # rendered UI column, so the rename is a breaking OpenAPI change delivering
    # zero capability. The two can coexist until a second source actually lands.
    #
    # On the table class so PlayerPublic is unaffected.
    source_id: uuid.UUID | None = Field(
        default=None, foreign_key="data_source.id", index=True
    )
    external_id: str | None = Field(default=None, max_length=64)


class PlayerPublic(PlayerBase):
    id: uuid.UUID
    match_count: int = 0


class PlayersPublic(SQLModel):
    data: list[PlayerPublic]
    count: int
