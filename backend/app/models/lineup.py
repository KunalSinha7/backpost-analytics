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
    # Mirrors the migration's constraint so autogenerate does not emit a DROP
    # for a constraint the model metadata does not know about.
    __table_args__ = (
        UniqueConstraint(
            "match_id", "statsbomb_player_id", name="uq_lineup_match_statsbomb_player"
        ),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    team_id: uuid.UUID = Field(foreign_key="team.id", index=True)
    player_id: uuid.UUID = Field(foreign_key="player.id", index=True)
    # On the table class, not the Base, to keep it out of LineupPublic.
    #
    # none_as_null makes SQL NULL mean "never captured": without it SQLAlchemy
    # writes Python None as the JSON `null` literal, which IS NOT NULL matches,
    # making an uncaptured payload indistinguishable from a captured empty one.
    raw: dict | None = Field(
        default=None, sa_column=Column(JSONB(none_as_null=True), nullable=True)
    )


class LineupPublic(LineupBase):
    # Player and team names are resolved from the FKs rather than stored on
    # every appearance.
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
