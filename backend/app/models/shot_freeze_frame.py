import uuid

from sqlmodel import Field, SQLModel


class ShotFreezeFrame(SQLModel, table=True):
    """One visible player's position at the instant of a shot.

    Backfilled from `event.raw_event['shot_freeze_frame']` — the dedicated
    `frame360` table holds 0 rows in practice, so this is the only positional
    context actually present in the database.

    `player_id`/`position_id` are nullable for the same reason as
    `MatchFormationSlot`: an id that fails to resolve should not cost the rest
    of the frame. `is_keeper` is not a raw StatsBomb field — it is derived
    from the frame entry's own `position.id == 1` ("Goalkeeper", the same
    vocabulary the tactics payload and the `position` table use).
    """

    __tablename__ = "shot_freeze_frame"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    event_id: uuid.UUID = Field(foreign_key="event.id", index=True)
    player_id: uuid.UUID | None = Field(
        default=None, foreign_key="player.id", index=True
    )
    position_id: uuid.UUID | None = Field(
        default=None, foreign_key="position.id", index=True
    )
    location_x: float | None = None
    location_y: float | None = None
    is_teammate: bool = False
    is_keeper: bool = False
