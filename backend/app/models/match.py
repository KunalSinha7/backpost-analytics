import uuid

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.models.competition import CompetitionSeason


class SoccerMatchBase(SQLModel):
    statsbomb_id: int = Field(index=True, unique=True)
    # Indexed: listing competitions correlates on this column, and without it
    # the planner seq-scans soccer_match once per competition.
    competition_season_id: uuid.UUID = Field(
        foreign_key="competition_season.id", index=True
    )
    match_date: str = Field(max_length=20)
    kick_off: str | None = Field(default=None, max_length=20)
    home_score: int | None = None
    away_score: int | None = None
    stadium: str | None = Field(default=None, max_length=255)
    referee: str | None = Field(default=None, max_length=255)
    match_week: int | None = None
    competition_stage_name: str | None = Field(default=None, max_length=100)
    home_team_gender: str | None = Field(default=None, max_length=20)
    away_team_gender: str | None = Field(default=None, max_length=20)
    home_team_country_name: str | None = Field(default=None, max_length=100)
    away_team_country_name: str | None = Field(default=None, max_length=100)
    home_team_group: str | None = Field(default=None, max_length=50)
    away_team_group: str | None = Field(default=None, max_length=50)
    home_manager_name: str | None = Field(default=None, max_length=255)
    away_manager_name: str | None = Field(default=None, max_length=255)
    match_status: str | None = Field(default=None, max_length=50)
    last_updated: str | None = Field(default=None, max_length=50)
    match_status_360: str | None = Field(default=None, max_length=50)
    home_team_id: uuid.UUID = Field(foreign_key="team.id", index=True)
    away_team_id: uuid.UUID = Field(foreign_key="team.id", index=True)


# Fields dropped from `SoccerMatchPublic.from_row`'s dump — kept off
# `SoccerMatchBase` deliberately, see the comment on `SoccerMatch` below.
_TABLE_ONLY_FIELDS = {
    "raw",
    "referee_id",
    "stadium_id",
    "home_manager_id",
    "away_manager_id",
    "competition_stage_id",
}


class SoccerMatch(SoccerMatchBase, table=True):
    __tablename__ = "soccer_match"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    competition_season: CompetitionSeason | None = Relationship(
        back_populates="matches"
    )
    # On the table class, not the Base, to keep it out of SoccerMatchPublic.
    # none_as_null: see the note on Lineup.raw.
    raw: dict | None = Field(
        default=None, sa_column=Column(JSONB(none_as_null=True), nullable=True)
    )
    # Deferred entities (issue #30): nullable FKs alongside the free-text
    # columns above (`referee`, `stadium`, `home_manager_name`,
    # `away_manager_name`, `competition_stage_name`), which are left in place.
    # Nothing reads these yet — same "expand only" shape as Phase 1's
    # identity work — so, like `raw`, they stay off the Base/Public contract
    # rather than becoming part of the API surface for no consumer.
    referee_id: uuid.UUID | None = Field(
        default=None, foreign_key="referee.id", index=True
    )
    stadium_id: uuid.UUID | None = Field(
        default=None, foreign_key="stadium.id", index=True
    )
    home_manager_id: uuid.UUID | None = Field(
        default=None, foreign_key="manager.id", index=True
    )
    away_manager_id: uuid.UUID | None = Field(
        default=None, foreign_key="manager.id", index=True
    )
    competition_stage_id: uuid.UUID | None = Field(
        default=None, foreign_key="competition_stage.id", index=True
    )


class SoccerMatchPublic(SoccerMatchBase):
    # Team names are resolved from the FKs by the repository, which selects
    # them as labelled columns in the same query.

    id: uuid.UUID
    home_team: str = Field(max_length=255)
    away_team: str = Field(max_length=255)
    has_events: bool = False

    @classmethod
    def from_row(
        cls,
        match: "SoccerMatch",
        home_team: str,
        away_team: str,
        *,
        has_events: bool = False,
    ) -> "SoccerMatchPublic":
        """Build the response from a row plus its joined team names.

        Explicit rather than `model_validate(match)`: the names are no longer
        attributes of the row, so validation would fail on two required fields.
        `raw` is excluded because it is table-only — it holds the whole source
        payload and has never been part of the contract.
        """
        return cls(
            **match.model_dump(exclude=_TABLE_ONLY_FIELDS),
            home_team=home_team,
            away_team=away_team,
            has_events=has_events,
        )


class SoccerMatchesPublic(SQLModel):
    data: list[SoccerMatchPublic]
    count: int


class SoccerTeamsPublic(SQLModel):
    data: list[str]
