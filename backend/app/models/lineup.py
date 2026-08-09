import uuid

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class LineupBase(SQLModel):
    match_id: uuid.UUID = Field(foreign_key="soccer_match.id", index=True)
    team_name: str = Field(max_length=255)
    statsbomb_player_id: int
    player_name: str = Field(max_length=255)
    player_nickname: str | None = Field(default=None, max_length=255)
    jersey_number: int
    country_name: str | None = Field(default=None, max_length=100)
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
    team_id: uuid.UUID | None = Field(default=None, foreign_key="team.id", index=True)
    player_id: uuid.UUID | None = Field(
        default=None, foreign_key="player.id", index=True
    )
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
    id: uuid.UUID


class LineupsPublic(SQLModel):
    data: list[LineupPublic]
    count: int
