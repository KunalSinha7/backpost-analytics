import uuid

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Team(SQLModel, table=True):
    """A club or national side, identified by the source's own id."""

    # Mirrors the migration's constraint so autogenerate does not emit a DROP
    # for a constraint the model metadata does not know about.
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_team_source_ext"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(foreign_key="data_source.id", index=True)
    # varchar, not int: sources use ints, uuids and opaque strings. This paired
    # with source_id — never the name — is what identity means here.
    external_id: str = Field(max_length=64)
    # The canonical display name; other spellings live in `team_alias`.
    name: str = Field(max_length=255, index=True)
    # Nullable: not every feed supplies these.
    gender: str | None = Field(default=None, max_length=20)
    country_name: str | None = Field(default=None, max_length=100)


class TeamAlias(SQLModel, table=True):
    """Every distinct name a source has used for a team.

    Lets a lookup by any spelling — "Marseille" or "Olympique de Marseille" —
    find the same team, and preserves the original strings, which survive
    nowhere else.
    """

    __tablename__ = "team_alias"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint(
            "team_id", "source_id", "name", name="uq_team_alias_team_source_name"
        ),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    team_id: uuid.UUID = Field(foreign_key="team.id", index=True)
    source_id: uuid.UUID = Field(foreign_key="data_source.id", index=True)
    name: str = Field(max_length=255, index=True)
