import uuid

from sqlmodel import Field, SQLModel


class Position(SQLModel, table=True):
    """A playing position, e.g. "Right Center Forward" (24 values in StatsBomb).

    Carries source columns like `team` and `player` rather than a bare name:
    position vocabularies are provider-specific, so a second source's id `1`
    is not this source's id `1`.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(foreign_key="data_source.id", index=True)
    external_id: str = Field(max_length=64)
    name: str = Field(max_length=100, index=True)
