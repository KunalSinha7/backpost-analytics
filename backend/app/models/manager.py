import uuid

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Manager(SQLModel, table=True):
    """A team manager, identified by the source's own id.

    Shared by both sides of a match — `soccer_match.home_manager_id` and
    `away_manager_id` both point here, there is no separate "home manager"
    entity. Deferred out of the original normalization plan (issue #30): no
    analytics use case existed at the time, only the same identity argument
    every other entity here carries. Follows the same `(source_id,
    external_id)` convention as `team` / `position`.
    """

    # Mirrors the migration's constraint so autogenerate does not emit a DROP
    # for a constraint the model metadata does not know about.
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_manager_source_ext"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(foreign_key="data_source.id", index=True)
    external_id: str = Field(max_length=64)
    name: str = Field(max_length=255, index=True)
