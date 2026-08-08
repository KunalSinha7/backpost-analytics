import uuid

from sqlmodel import Field, SQLModel


class DataSource(SQLModel, table=True):
    """A provider of ingested soccer data, e.g. StatsBomb.

    No `*Public` schema: there is no API surface for sources today. Entities
    gain `source_id` / `external_id` in a later phase; this table is the target.
    """

    __tablename__ = "data_source"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(max_length=50, unique=True, index=True)
    name: str = Field(max_length=255)
