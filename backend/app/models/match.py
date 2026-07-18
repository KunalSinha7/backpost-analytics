import uuid

from sqlmodel import Field, Relationship, SQLModel

from app.models.competition import Competition


class SoccerMatchBase(SQLModel):
    statsbomb_id: int = Field(index=True, unique=True)
    competition_id: uuid.UUID = Field(foreign_key="competition.id")
    match_date: str = Field(max_length=20)
    kick_off: str | None = Field(default=None, max_length=20)
    home_team: str = Field(max_length=255)
    away_team: str = Field(max_length=255)
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


class SoccerMatch(SoccerMatchBase, table=True):
    __tablename__ = "soccer_match"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    competition: Competition | None = Relationship(back_populates="matches")


class SoccerMatchPublic(SoccerMatchBase):
    id: uuid.UUID


class SoccerMatchesPublic(SQLModel):
    data: list[SoccerMatchPublic]
    count: int
