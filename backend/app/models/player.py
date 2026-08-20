import uuid

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class PlayerBase(SQLModel):
    statsbomb_id: int = Field(unique=True, index=True)
    name: str = Field(max_length=255, index=True)
    nickname: str | None = Field(default=None, max_length=255)
    nationality: str | None = Field(default=None, max_length=100)


class Player(PlayerBase, table=True):
    # Mirrors the migration's constraint so autogenerate does not emit a DROP
    # for a constraint the model metadata does not know about.
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_player_source_ext"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Nullable, and alongside the older `statsbomb_id` rather than replacing
    # it: that column is part of the public API and cannot be renamed without
    # breaking clients.
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
    """Appearances, minutes and per-90 event rates for one player."""

    player_id: uuid.UUID
    player_name: str
    season_id: uuid.UUID | None = None
    appearances: int
    minutes_played: float
    stats: list[PlayerStatLine]
