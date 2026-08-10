import uuid

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.models.competition import CompetitionSeason


class SoccerMatchBase(SQLModel):
    statsbomb_id: int = Field(index=True, unique=True)
    # Renamed from `competition_id` in Phase 2. After the split that name is
    # actively wrong: a `competition` table now exists and means the timeless
    # entity, so `competition_id` here would point at an edition while reading
    # as though it pointed at La Liga. Unlike the `statsbomb_id` rename that
    # §6/H1 cut, this one is not cosmetic — leaving it makes the schema lie.
    #
    # Indexed: /competitions?has_events=true correlates on this column, and
    # without it the planner seq-scans soccer_match once per competition —
    # measured at 14,136 ms vs 11.5 ms with the index on the same data.
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
    # NOT NULL as of Phase 4 — verified 0 nulls across all 3,961 rows before the
    # constraint was applied. Team identity now lives in one place; the
    # `home_team`/`away_team` strings that used to sit beside these are gone
    # from the table and are resolved for the API instead (see
    # SoccerMatchPublic).
    home_team_id: uuid.UUID = Field(foreign_key="team.id", index=True)
    away_team_id: uuid.UUID = Field(foreign_key="team.id", index=True)


class SoccerMatch(SoccerMatchBase, table=True):
    __tablename__ = "soccer_match"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    competition_season: CompetitionSeason | None = Relationship(
        back_populates="matches"
    )
    # Declared here and not on SoccerMatchBase so it stays out of
    # SoccerMatchPublic — same placement as Event.raw_event.
    # none_as_null: see the note on Lineup.raw.
    raw: dict | None = Field(
        default=None, sa_column=Column(JSONB(none_as_null=True), nullable=True)
    )


class SoccerMatchPublic(SoccerMatchBase):
    # The API contract, unchanged — but no longer backed by stored strings.
    #
    # §3's rule is that the strings leave the *tables*, not the *API*. These two
    # fields used to be columns on `soccer_match`, duplicated on every one of the
    # 3,961 rows and free to drift from `team.name` — which is exactly how the
    # Marseille bug happened. They are now resolved through `home_team_id` /
    # `away_team_id` by the repository, which selects them as labelled columns in
    # the same query rather than traversing a relationship.

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
            **match.model_dump(exclude={"raw"}),
            home_team=home_team,
            away_team=away_team,
            has_events=has_events,
        )


class SoccerMatchesPublic(SQLModel):
    data: list[SoccerMatchPublic]
    count: int


class SoccerTeamsPublic(SQLModel):
    data: list[str]
