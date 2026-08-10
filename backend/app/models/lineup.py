import uuid

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.player import Player


class LineupBase(SQLModel):
    match_id: uuid.UUID = Field(foreign_key="soccer_match.id", index=True)
    statsbomb_player_id: int
    jersey_number: int
    started: bool = Field(default=False)


class Lineup(LineupBase, table=True):
    # Declared here as well as in the migration so the model metadata matches
    # the database. Without it `alembic revision --autogenerate` sees a
    # constraint the models do not know about and emits a DROP for it on every
    # future migration — which only has to be accepted once to silently remove
    # the guarantee.
    __table_args__ = (
        UniqueConstraint(
            "match_id", "statsbomb_player_id", name="uq_lineup_match_statsbomb_player"
        ),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # On the table class, not LineupBase: LineupPublic must not change shape in
    # this phase. `team_name` / `statsbomb_player_id` keep serving the API.
    #
    # team_id is resolved through the *event* feed, never against the parent
    # match's two teams — see §1.6/B0. Scoping a name comparison to two
    # candidates is not an id match, and it fails on the 20 Marseille rows.
    # NOT NULL as of Phase 4 — 0 nulls across all 13,650 rows.
    team_id: uuid.UUID = Field(foreign_key="team.id", index=True)
    player_id: uuid.UUID = Field(foreign_key="player.id", index=True)
    # Declared here and not on LineupBase so it stays out of LineupPublic —
    # same placement as Event.raw_event. SQL NULL means "ingested before this
    # column existed", as distinct from a captured-but-empty payload.
    #
    # none_as_null is what makes that distinction real: without it SQLAlchemy
    # writes Python None as the JSON `null` literal, which is IS NOT NULL in
    # SQL, so "never captured" becomes indistinguishable from "captured null".
    raw: dict | None = Field(
        default=None, sa_column=Column(JSONB(none_as_null=True), nullable=True)
    )


class LineupPublic(LineupBase):
    # The API contract, unchanged — names resolved through the FKs.
    #
    # `player_name` and `player_nickname` were duplicated onto every one of a
    # player's appearances; `team_name` onto every squad member of every match.
    # They now come from `player` and `team`, which is what §1.3 meant by player
    # identity being split three ways with no FK.

    id: uuid.UUID
    team_name: str = Field(max_length=255)
    player_name: str = Field(max_length=255)
    player_nickname: str | None = Field(default=None, max_length=255)
    country_name: str | None = Field(default=None, max_length=100)

    @classmethod
    def from_row(
        cls, lineup: "Lineup", team_name: str, player: "Player"
    ) -> "LineupPublic":
        return cls(
            **lineup.model_dump(exclude={"raw"}),
            team_name=team_name,
            player_name=player.name,
            player_nickname=player.nickname,
            country_name=player.nationality,
        )


class LineupsPublic(SQLModel):
    data: list[LineupPublic]
    count: int
