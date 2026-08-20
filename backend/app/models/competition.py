import uuid

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


class Competition(SQLModel, table=True):
    """A competition independent of any season: La Liga, not La Liga 2018/2019.

    One row per competition, however many seasons it has run. The
    season-specific pairing lives in `CompetitionSeason`.
    """

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_competition_source_ext"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(foreign_key="data_source.id", index=True)
    external_id: str = Field(max_length=64)
    name: str = Field(max_length=255, index=True)
    country_name: str = Field(max_length=100)
    gender: str = Field(max_length=20)
    is_youth: bool = False
    is_international: bool = False


class Season(SQLModel, table=True):
    """A season: "2018/2019", or "1958" for single-year tournaments.

    Deliberately has no start/end year: single-year tournament names cannot be
    split into two meaningful years, and nothing needs them.
    """

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_season_source_ext"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(foreign_key="data_source.id", index=True)
    external_id: str = Field(max_length=64)
    name: str = Field(max_length=100, index=True)


class CompetitionSeasonBase(SQLModel):
    """One competition in one season — e.g. La Liga 2018/2019."""

    statsbomb_id: int = Field(index=True)
    season_id: int = Field(index=True)
    match_updated: str | None = Field(default=None, max_length=50)
    match_available: str | None = Field(default=None, max_length=50)
    match_updated_360: str | None = Field(default=None, max_length=50)
    match_available_360: str | None = Field(default=None, max_length=50)


class CompetitionSeason(CompetitionSeasonBase, table=True):
    __tablename__ = "competition_season"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("statsbomb_id", "season_id"),)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    matches: list["SoccerMatch"] = Relationship(  # type: ignore  # noqa: F821
        back_populates="competition_season", cascade_delete=True
    )
    competition_id: uuid.UUID = Field(foreign_key="competition.id", index=True)
    # Not named `season_id`: that name is taken by StatsBomb's integer season
    # id above, which is part of the public API response and cannot be renamed
    # without breaking clients.
    season_ref_id: uuid.UUID = Field(foreign_key="season.id", index=True)
    # none_as_null: see the note on Lineup.raw.
    raw: dict | None = Field(
        default=None, sa_column=Column(JSONB(none_as_null=True), nullable=True)
    )


class CompetitionPublic(CompetitionSeasonBase):
    id: uuid.UUID
    country_name: str = Field(max_length=100)
    competition_name: str = Field(max_length=255)
    competition_gender: str = Field(max_length=20)
    competition_youth: bool = False
    competition_international: bool = False
    season_name: str = Field(max_length=100)
    match_count: int = 0

    @classmethod
    def from_row(
        cls,
        edition: "CompetitionSeason",
        competition: "Competition",
        season: "Season",
        *,
        match_count: int = 0,
    ) -> "CompetitionPublic":
        return cls(
            **edition.model_dump(exclude={"raw"}),
            country_name=competition.country_name,
            competition_name=competition.name,
            competition_gender=competition.gender,
            competition_youth=competition.is_youth,
            competition_international=competition.is_international,
            season_name=season.name,
            match_count=match_count,
        )


class CompetitionsPublic(SQLModel):
    data: list[CompetitionPublic]
    count: int
