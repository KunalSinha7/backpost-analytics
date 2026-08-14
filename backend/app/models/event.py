import uuid

from sqlalchemy import JSON, Index
from sqlmodel import Field, SQLModel


class EventBase(SQLModel):
    statsbomb_id: str = Field(max_length=36, index=True, unique=True)
    match_id: uuid.UUID = Field(foreign_key="soccer_match.id")
    index: int
    period: int
    timestamp: str | None = Field(default=None, max_length=20)
    minute: int
    second: int
    type_name: str = Field(max_length=100)
    possession: int | None = None
    play_pattern_name: str | None = Field(default=None, max_length=100)
    location_x: float | None = None
    location_y: float | None = None
    end_location_x: float | None = None
    end_location_y: float | None = None
    duration: float | None = None
    under_pressure: bool | None = None
    off_camera: bool | None = None
    out: bool | None = None


class Event(EventBase, table=True):
    # Composite rather than a plain index=True on match_id: every read of this
    # table is "the events of one match, in index order", so the second column
    # serves the ORDER BY as well as the lookup. A leading-column-only index
    # would be redundant with this one.
    __table_args__ = (Index("ix_event_match_id_index", "match_id", "index"),)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    raw_event: dict = Field(default_factory=dict, sa_type=JSON)
    # All on the table class, not EventBase: EventPublic must not change shape.
    # `team` / `player` / `pass_recipient` keep serving the API unchanged, and
    # the ids below are populated beside them for the season-stats query.
    #
    # Backfilled from raw_event, which covers 100% of rows — no re-fetch. Note
    # the ids arrive as float strings ("7626.0") because pandas widens nullable
    # int columns to float64, so casts must go ::numeric::bigint; a bare ::int
    # throws (§1.5/B1).
    # team_id/player_id are deliberately NOT index=True. §2.2 specifies the
    # composite indexes (player_id, match_id) and (team_id, match_id) for the
    # season-stats query in Phase 3; single-column indexes here would be
    # redundant with those (same leading column) and would have to be dropped
    # again. Same reasoning that made ix_event_match_id_index composite.
    # NOT NULL as of Phase 4 — 0 nulls across all 1,365,934 rows. player_id
    # and pass_recipient_id stay nullable: 5,516 events (Half Start, Half End
    # and friends) genuinely have no player, and forcing a value there would
    # mean inventing one.
    team_id: uuid.UUID = Field(foreign_key="team.id")
    possession_team_id: uuid.UUID = Field(foreign_key="team.id")
    player_id: uuid.UUID | None = Field(default=None, foreign_key="player.id")
    pass_recipient_id: uuid.UUID | None = Field(default=None, foreign_key="player.id")
    position_id: uuid.UUID | None = Field(default=None, foreign_key="position.id")
    substitution_replacement_id: uuid.UUID | None = Field(
        default=None, foreign_key="player.id"
    )


class EventPublic(EventBase):
    # The API contract, unchanged — names resolved rather than stored.
    #
    # §6 warns specifically about this path: `read_events` defaults to
    # `limit=10000`, so resolving these through ORM relationships would mean up
    # to four lazy loads per row. The service instead builds one id -> name map
    # per match (at most two teams and a few dozen players) and maps in memory.

    id: uuid.UUID
    team: str = Field(max_length=255)
    player: str | None = Field(default=None, max_length=255)
    pass_recipient: str | None = Field(default=None, max_length=255)
    possession_team_name: str | None = Field(default=None, max_length=255)

    @classmethod
    def from_row(
        cls,
        event: "Event",
        names: "dict[uuid.UUID, str]",
    ) -> "EventPublic":
        return cls(
            **event.model_dump(
                exclude={
                    "raw_event",
                    "team_id",
                    "possession_team_id",
                    "player_id",
                    "pass_recipient_id",
                    "position_id",
                    "substitution_replacement_id",
                }
            ),
            team=names.get(event.team_id, ""),
            player=names.get(event.player_id) if event.player_id else None,
            pass_recipient=(
                names.get(event.pass_recipient_id) if event.pass_recipient_id else None
            ),
            possession_team_name=(
                names.get(event.possession_team_id)
                if event.possession_team_id
                else None
            ),
        )


class EventsPublic(SQLModel):
    data: list[EventPublic]
    count: int
