import uuid

from sqlmodel import Field, SQLModel


class Team(SQLModel, table=True):
    """A club or national side, identified by the source's own id.

    No `*Public` schema yet: Phase 1 exposes team ids on `SoccerMatchPublic`
    but has no `/teams` endpoint, and a schema nothing serializes is dead
    weight. Same reasoning as `DataSource`.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(foreign_key="data_source.id", index=True)
    # varchar, not int: sources use ints, uuids and opaque strings. Paired with
    # source_id under a UNIQUE constraint (see the migration) — that pair, never
    # the name, is what identity means here.
    external_id: str = Field(max_length=64)
    # The canonical display name. Where feeds disagree — StatsBomb's match feed
    # says "Olympique de Marseille" while its event feed says "Marseille" — the
    # match-feed name wins, because that is the string the API emits today.
    # Every variant seen is retained in `team_alias`.
    name: str = Field(max_length=255, index=True)
    # Both nullable by necessity: a team first seen through the event feed
    # carries neither. Only the match feed supplies them.
    gender: str | None = Field(default=None, max_length=20)
    country_name: str | None = Field(default=None, max_length=100)


class TeamAlias(SQLModel, table=True):
    """Every distinct name a source has used for a team.

    Collapsing {"Marseille", "Olympique de Marseille"} into one `team` row is
    irreversible, and the per-feed strings survive nowhere else once the
    denormalized columns are dropped in Phase 4. Recording them as the resolver
    goes is what keeps that merge auditable — and Phase 4 reversible.
    """

    __tablename__ = "team_alias"  # type: ignore[assignment]
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    team_id: uuid.UUID = Field(foreign_key="team.id", index=True)
    source_id: uuid.UUID = Field(foreign_key="data_source.id", index=True)
    name: str = Field(max_length=255, index=True)
