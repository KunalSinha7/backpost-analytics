import uuid

from sqlmodel import Field, SQLModel


class LineupPosition(SQLModel, table=True):
    """One stint a player spent on the pitch in a given position.

    A player who starts, shifts position, and is subbed off has three stints.

    Times are seconds from kick-off, not the source's "MM:SS" strings, which
    `lineup.raw` already preserves verbatim.

    `to_seconds` is NOT NULL: a stint still running at the final whistle is
    resolved to the match's last event when the row is written, so minutes are
    a plain subtraction. `end_reason` still records why the stint ended.
    """

    __tablename__ = "lineup_position"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    lineup_id: uuid.UUID = Field(foreign_key="lineup.id", index=True)
    position_id: uuid.UUID = Field(foreign_key="position.id", index=True)
    from_period: int
    to_period: int
    from_seconds: int
    to_seconds: int
    start_reason: str = Field(max_length=100)
    end_reason: str = Field(max_length=100)

    @property
    def duration_seconds(self) -> int:
        return max(self.to_seconds - self.from_seconds, 0)
