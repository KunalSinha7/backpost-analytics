import uuid

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class PlayerBase(SQLModel):
    statsbomb_id: int = Field(unique=True, index=True)
    name: str = Field(max_length=255, index=True)
    nickname: str | None = Field(default=None, max_length=255)
    nationality: str | None = Field(default=None, max_length=100)


class Player(PlayerBase, table=True):
    # Declared here as well as in the migration so the model metadata matches
    # the database. Without it `alembic revision --autogenerate` sees a
    # constraint the models do not know about and emits a DROP for it on every
    # future migration — which only has to be accepted once to silently remove
    # the guarantee.
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_player_source_ext"),
    )
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


class PlayerStatLine(SQLModel):
    """One event type and how often the player produced it."""

    type_name: str
    count: int
    per_90: float


class PlayerSeasonStats(SQLModel):
    """Season stats for one player — the capability §1.3 set out to enable.

    Before this, answering it meant a 4-hop string-mediated join across 376k
    unindexed rows, and minutes played were unavailable at any price because
    they lived inside a JSON array.
    """

    player_id: uuid.UUID
    player_name: str
    season_id: uuid.UUID | None = None
    appearances: int
    minutes_played: float
    stats: list[PlayerStatLine]
