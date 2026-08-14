import uuid

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


class Competition(SQLModel, table=True):
    """The TIMELESS competition: La Liga, not La Liga 2018/2019.

    This inverts what the name meant before Phase 2. The old `competition`
    table was really an *edition* — one row per (competition, season) pair —
    which is why La Liga's name, country and gender were stored 18 times over.
    That is the 2NF violation in §1.1: those attributes depend on
    `statsbomb_id` alone, not on the whole key.

    StatsBomb uses "competition" the same way (`competition_id=11` is La Liga
    across every season), as do Opta and Wyscout, so this is domain vocabulary
    rather than vendor jargon (§2.1).
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

    No `start_year`/`end_year`. They are undefined for the single-year names
    the data actually contains (the 1958 World Cup) and nothing reads them, so
    §6/Cuts drops them rather than shipping a column that is null or wrong on
    day one.
    """

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_season_source_ext"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(foreign_key="data_source.id", index=True)
    external_id: str = Field(max_length=64)
    name: str = Field(max_length=100, index=True)


class CompetitionSeasonBase(SQLModel):
    """The EDITION — one row per (competition, season).

    Field names are unchanged from the pre-split `CompetitionBase` on purpose:
    `CompetitionPublic` inherits from this, and the Phase 2 gate is that the
    `/competitions` response is byte-identical. The columns become redundant
    with the FKs below once those are populated, and Phase 4 drops them.
    """

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
    # On the table class, not the Base, so CompetitionPublic keeps its exact
    # current shape.
    # NOT NULL as of Phase 4 — 0 nulls across all 80 editions.
    competition_id: uuid.UUID = Field(foreign_key="competition.id", index=True)
    # Named `season_ref_id` rather than `season_id` only because the legacy
    # integer `season_id` above — StatsBomb's own season id, and a public API
    # field — still occupies that name during expand. Phase 4 drops the legacy
    # column and renames this one to `season_id`. Carrying both for a phase is
    # what expand/contract costs; the alternative is a breaking API change now.
    season_ref_id: uuid.UUID = Field(foreign_key="season.id", index=True)
    # none_as_null: see the note on Lineup.raw.
    raw: dict | None = Field(
        default=None, sa_column=Column(JSONB(none_as_null=True), nullable=True)
    )


class CompetitionPublic(CompetitionSeasonBase):
    # The API contract, unchanged — attributes resolved through the FKs.
    #
    # These six fields were the 2NF violation itself (§1.1): they depend on the
    # competition or the season alone, yet were stored on every edition, so
    # La Liga's name and country sat on 18 rows. They now come from `competition`
    # and `season`, and the edition row keeps only what is genuinely its own.

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
