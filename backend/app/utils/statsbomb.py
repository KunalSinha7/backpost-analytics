import math

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _clean_nan(data: dict) -> dict:
    result = {}
    for k, v in data.items():
        if isinstance(v, float) and math.isnan(v):
            result[k] = None
        elif isinstance(v, dict):
            result[k] = _clean_nan(v)
        elif isinstance(v, list):
            result[k] = [
                None if (isinstance(i, float) and math.isnan(i)) else i for i in v
            ]
        else:
            result[k] = v
    return result


class _StatsBombRow(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def preprocess(cls, data: dict) -> dict:
        return _clean_nan(data)


class StatsBombCompetitionRow(_StatsBombRow):
    competition_id: int
    season_id: int
    country_name: str = ""
    competition_name: str = ""
    competition_gender: str = "male"
    competition_youth: bool = False
    competition_international: bool = False
    season_name: str = ""
    match_updated: str | None = None
    match_available: str | None = None
    match_updated_360: str | None = None
    match_available_360: str | None = None


class StatsBombMatchRow(_StatsBombRow):
    match_id: int
    match_date: str = ""
    kick_off: str | None = None
    home_team: str = ""
    away_team: str = ""
    home_score: int | None = None
    away_score: int | None = None
    stadium: str | None = None
    referee: str | None = None
    match_week: int | None = None
    competition_stage: str | None = None
    home_team_gender: str | None = None
    away_team_gender: str | None = None
    home_team_country_name: str | None = None
    away_team_country_name: str | None = None
    home_team_group: str | None = None
    away_team_group: str | None = None
    home_manager_name: str | None = None
    away_manager_name: str | None = None
    match_status: str | None = None
    last_updated: str | None = None
    match_status_360: str | None = None


class StatsBombEventRow(_StatsBombRow):
    model_config = ConfigDict(extra="allow")

    id: str
    index: int
    period: int
    timestamp: str | None = None
    minute: int
    second: int
    type: str | None = None
    possession: int | None = None
    possession_team: str | None = None
    play_pattern: str | None = None
    team: str | None = None
    player: str | None = None
    location: list[float] | None = None
    duration: float | None = None
    under_pressure: bool | None = None
    off_camera: bool | None = None
    out: bool | None = None

    @field_validator("type", "team", "player", "possession_team", "play_pattern", mode="before")
    @classmethod
    def extract_name(cls, v: object) -> str | None:
        if isinstance(v, dict):
            return v.get("name")
        return v  # type: ignore[return-value]


class StatsBombLineupPlayerRow(_StatsBombRow):
    player_id: int
    player_name: str = ""
    player_nickname: str | None = None
    jersey_number: int = 0
    country: str | None = None
    positions: list = []

    @field_validator("country", mode="before")
    @classmethod
    def extract_country_name(cls, v: object) -> str | None:
        if isinstance(v, dict):
            return v.get("name")
        return v  # type: ignore[return-value]

    def is_starter(self) -> bool:
        return bool(self.positions) and self.positions[0].get("start_reason") == "Starting XI"


class StatsBombFrameRow(_StatsBombRow):
    model_config = ConfigDict(extra="allow")

    id: str = ""
    visible_area: list = []
    freeze_frame: list = []
