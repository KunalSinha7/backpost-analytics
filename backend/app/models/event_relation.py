import uuid

from sqlmodel import Field, SQLModel


class EventRelation(SQLModel, table=True):
    """One directed edge of StatsBomb's `related_events` graph.

    The source field is symmetric — a pass and its ball receipt each list the
    other in their own `related_events` array — and this table stores it
    exactly as given: one row per array entry, so both directions exist as
    independent rows. See the backfill migration for why that was chosen over
    canonicalising to a single direction plus a UNION at query time.

    No surrogate `id`: the pair is the identity, and PostgreSQL enforces "no
    duplicate edge" for free via the composite primary key rather than a
    UNIQUE constraint bolted onto a meaningless synthetic key.
    """

    __tablename__ = "event_relation"  # type: ignore[assignment]
    event_id: uuid.UUID = Field(
        foreign_key="event.id", primary_key=True, ondelete="CASCADE"
    )
    related_event_id: uuid.UUID = Field(
        foreign_key="event.id",
        primary_key=True,
        ondelete="CASCADE",
        index=True,
    )
