import uuid

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


class CompetitionBase(SQLModel):
    statsbomb_id: int = Field(index=True)
    season_id: int = Field(index=True)
    country_name: str = Field(max_length=100)
    competition_name: str = Field(max_length=255)
    competition_gender: str = Field(max_length=20)
    competition_youth: bool = False
    competition_international: bool = False
    season_name: str = Field(max_length=100)
    match_updated: str | None = Field(default=None, max_length=50)
    match_available: str | None = Field(default=None, max_length=50)
    match_updated_360: str | None = Field(default=None, max_length=50)
    match_available_360: str | None = Field(default=None, max_length=50)


class Competition(CompetitionBase, table=True):
    __table_args__ = (UniqueConstraint("statsbomb_id", "season_id"),)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    matches: list["SoccerMatch"] = Relationship(  # type: ignore  # noqa: F821
        back_populates="competition", cascade_delete=True
    )
    # Declared here and not on CompetitionBase so it stays out of
    # CompetitionPublic — same placement as Event.raw_event.
    raw: dict | None = Field(default=None, sa_type=JSONB)


class CompetitionPublic(CompetitionBase):
    id: uuid.UUID
    match_count: int = 0


class CompetitionsPublic(SQLModel):
    data: list[CompetitionPublic]
    count: int
