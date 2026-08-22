import uuid

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class CompetitionStage(SQLModel, table=True):
    """A stage within a competition (e.g. "Group Stage", "Final").

    Carries the source id rather than a bare name: stage vocabularies are
    provider-specific, like `position`. Deferred out of the original
    normalization plan (issue #30): no analytics use case existed at the
    time, only the same identity argument every other entity here carries.
    """

    __tablename__ = "competition_stage"  # type: ignore[assignment]
    # Mirrors the migration's constraint so autogenerate does not emit a DROP
    # for a constraint the model metadata does not know about.
    __table_args__ = (
        UniqueConstraint(
            "source_id", "external_id", name="uq_competition_stage_source_ext"
        ),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(foreign_key="data_source.id", index=True)
    external_id: str = Field(max_length=64)
    name: str = Field(max_length=100, index=True)
