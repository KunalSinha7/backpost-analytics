import uuid

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Position(SQLModel, table=True):
    """A playing position, e.g. "Right Center Forward" (24 values in StatsBomb).

    Carries source columns like `team` and `player` rather than a bare name:
    position vocabularies are provider-specific, so a second source's id `1`
    is not this source's id `1`.
    """

    # Declared here as well as in the migration so the model metadata matches
    # the database. Without it `alembic revision --autogenerate` sees a
    # constraint the models do not know about and emits a DROP for it on every
    # future migration — which only has to be accepted once to silently remove
    # the guarantee.
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_position_source_ext"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(foreign_key="data_source.id", index=True)
    external_id: str = Field(max_length=64)
    name: str = Field(max_length=100, index=True)
