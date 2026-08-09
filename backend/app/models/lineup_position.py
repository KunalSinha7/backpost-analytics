import uuid

from sqlmodel import Field, SQLModel


class LineupPosition(SQLModel, table=True):
    """One stint a player spent on the pitch in a given position.

    `lineup.positions[]` was a repeating group inside a JSON column — a 1NF
    violation, and the reason per-90 stats were impossible (§2.2). A player who
    starts, shifts position, and is subbed off has three stints; summing their
    durations is what "minutes played" means.

    Times are stored as **seconds from kick-off**, not as the source's "MM:SS"
    strings. The strings carry no information the integers lack, `lineup.raw`
    already preserves them verbatim, and storing a value beside its own parse is
    the kind of duplication this plan exists to remove.

    `to_seconds` is NOT NULL even though the source's `to` is null for 8,339 of
    15,276 stints. Null there means one specific thing — verified as an exact
    correlation, `to IS NULL` if and only if `end_reason = 'Final Whistle'` — so
    it is resolved to the match's last event during backfill. `end_reason` still
    records *why* the stint ended, so nothing is lost, and every minutes query
    becomes a plain subtraction instead of a coalesce against match duration.
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
