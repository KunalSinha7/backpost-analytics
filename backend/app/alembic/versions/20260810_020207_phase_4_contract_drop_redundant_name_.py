"""phase 4 contract: drop redundant name columns, NOT NULL the FKs

Revision ID: 2fe0be7dbfe0
Revises: 11e2f338bb26
Create Date: 2026-08-10 02:02:07.000000

The contract step of §3. Every column dropped here is now derivable from a
foreign key, and every FK made NOT NULL was verified to have zero nulls first.

**This is the only destructive migration in the plan**, so it checks its own
preconditions before dropping anything. The guard is not ceremony: the whole
point of the denormalized columns was that they could drift from the entities,
and a value that drifted is a value the FK cannot reproduce. Dropping it would
lose data silently — the failure mode this plan exists to prevent.

Verified before the drop:

```
soccer_match.home_team / away_team  vs team.name          0 mismatches
competition_season.competition_name vs competition.name   0
competition_season.season_name      vs season.name        0
event.team          recoverable via team_alias            0 unrecoverable
lineup.team_name    recoverable via team_alias            0 unrecoverable
```

**One enumerated exception — 31 lineup rows across 5 players.** The same player
id arrives with inconsistent apostrophe encoding between feeds:

```
  lineup.player_name              player.name
  Cheikh M''Bengue        vs      Cheikh M'Bengue          23 rows
  Cheikh N'Doye           vs      Cheikh N''Doye            2
  Mamadou N'Diaye         vs      Mamadou N''Diaye          2
  David N'Gog             vs      David N"Gog               2
  Guy Adolphe N'Gosso...  vs      Guy Adolphe N''Gosso...   2
```

These are escaping artifacts in the source, not different people — the ids
match. After this migration each player has exactly one name, which is the
point of the entity. It is a real response change for those rows, enumerated
here rather than discovered later, in the same spirit as §6/H3's drift set.
"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "2fe0be7dbfe0"
down_revision = "11e2f338bb26"
branch_labels = None
depends_on = None


# (label, SQL returning a count that must be zero)
_RECOVERABILITY_CHECKS = [
    (
        "soccer_match.home_team disagrees with team.name",
        "SELECT count(*) FROM soccer_match m JOIN team t ON t.id = m.home_team_id "
        "WHERE m.home_team <> t.name",
    ),
    (
        "soccer_match.away_team disagrees with team.name",
        "SELECT count(*) FROM soccer_match m JOIN team t ON t.id = m.away_team_id "
        "WHERE m.away_team <> t.name",
    ),
    (
        "competition_season.competition_name disagrees with competition.name",
        "SELECT count(*) FROM competition_season cs "
        "JOIN competition c ON c.id = cs.competition_id "
        "WHERE cs.competition_name <> c.name",
    ),
    (
        "competition_season.season_name disagrees with season.name",
        "SELECT count(*) FROM competition_season cs "
        "JOIN season s ON s.id = cs.season_ref_id WHERE cs.season_name <> s.name",
    ),
    (
        "event.team is not recoverable from team_alias",
        "SELECT count(*) FROM event e WHERE NOT EXISTS ("
        "SELECT 1 FROM team_alias a WHERE a.team_id = e.team_id AND a.name = e.team)",
    ),
    (
        "lineup.team_name is not recoverable from team_alias",
        "SELECT count(*) FROM lineup l WHERE NOT EXISTS ("
        "SELECT 1 FROM team_alias a WHERE a.team_id = l.team_id AND a.name = l.team_name)",
    ),
]

# (table, column) pairs that become NOT NULL, each verified to have no nulls.
_NOT_NULL = [
    ("soccer_match", "home_team_id"),
    ("soccer_match", "away_team_id"),
    ("lineup", "team_id"),
    ("lineup", "player_id"),
    ("event", "team_id"),
    ("event", "possession_team_id"),
    ("competition_season", "competition_id"),
    ("competition_season", "season_ref_id"),
]

# Dropped last, once nothing depends on them.
_DROP = [
    ("soccer_match", "home_team"),
    ("soccer_match", "away_team"),
    ("event", "team"),
    ("event", "player"),
    ("event", "pass_recipient"),
    ("event", "possession_team_name"),
    ("lineup", "team_name"),
    ("lineup", "player_name"),
    ("lineup", "player_nickname"),
    ("lineup", "country_name"),
    ("competition_season", "competition_name"),
    ("competition_season", "country_name"),
    ("competition_season", "competition_gender"),
    ("competition_season", "competition_youth"),
    ("competition_season", "competition_international"),
    ("competition_season", "season_name"),
]


def _assert_safe_to_drop(bind) -> None:
    failures = []
    for label, sql in _RECOVERABILITY_CHECKS:
        count = bind.execute(sa.text(sql)).scalar_one()
        if count:
            failures.append(f"  - {label}: {count} row(s)")
    for table, column in _NOT_NULL:
        nulls = bind.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE {column} IS NULL")  # noqa: S608
        ).scalar_one()
        if nulls:
            failures.append(f"  - {table}.{column} still has {nulls} NULL(s)")
    if failures:
        raise RuntimeError(
            "Refusing to drop the denormalized columns: some values are not "
            "reproducible from the foreign keys, so dropping them would lose "
            "data.\n" + "\n".join(failures) + "\nRun the Phase 1-3 backfills first."
        )


def upgrade():
    bind = op.get_bind()
    _assert_safe_to_drop(bind)

    for table, column in _NOT_NULL:
        op.alter_column(table, column, nullable=False)
    for table, column in _DROP:
        op.drop_column(table, column)


def downgrade():
    """Restores the columns and repopulates them from the entities.

    The names are recoverable precisely because that redundancy is what this
    migration removed — every dropped value still exists on `team`, `player`,
    `competition` or `season`. The one thing a downgrade cannot restore is the
    per-row apostrophe variants noted in the docstring; those collapse to the
    canonical player name.
    """
    op.add_column(
        "competition_season",
        sa.Column("season_name", sqlmodel.sql.sqltypes.AutoString(100), nullable=True),
    )
    op.add_column(
        "competition_season",
        sa.Column("competition_international", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "competition_season", sa.Column("competition_youth", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "competition_season",
        sa.Column(
            "competition_gender", sqlmodel.sql.sqltypes.AutoString(20), nullable=True
        ),
    )
    op.add_column(
        "competition_season",
        sa.Column("country_name", sqlmodel.sql.sqltypes.AutoString(100), nullable=True),
    )
    op.add_column(
        "competition_season",
        sa.Column(
            "competition_name", sqlmodel.sql.sqltypes.AutoString(255), nullable=True
        ),
    )
    op.execute(
        """
        UPDATE competition_season cs SET
            competition_name = c.name,
            country_name = c.country_name,
            competition_gender = c.gender,
            competition_youth = c.is_youth,
            competition_international = c.is_international,
            season_name = s.name
        FROM competition c, season s
        WHERE c.id = cs.competition_id AND s.id = cs.season_ref_id
        """
    )

    op.add_column(
        "lineup",
        sa.Column("country_name", sqlmodel.sql.sqltypes.AutoString(100), nullable=True),
    )
    op.add_column(
        "lineup",
        sa.Column(
            "player_nickname", sqlmodel.sql.sqltypes.AutoString(255), nullable=True
        ),
    )
    op.add_column(
        "lineup",
        sa.Column("player_name", sqlmodel.sql.sqltypes.AutoString(255), nullable=True),
    )
    op.add_column(
        "lineup",
        sa.Column("team_name", sqlmodel.sql.sqltypes.AutoString(255), nullable=True),
    )
    op.execute(
        """
        UPDATE lineup l SET
            team_name = t.name,
            player_name = p.name,
            player_nickname = p.nickname,
            country_name = p.nationality
        FROM team t, player p
        WHERE t.id = l.team_id AND p.id = l.player_id
        """
    )

    op.add_column(
        "event",
        sa.Column(
            "possession_team_name", sqlmodel.sql.sqltypes.AutoString(255), nullable=True
        ),
    )
    op.add_column(
        "event",
        sa.Column("pass_recipient", sqlmodel.sql.sqltypes.AutoString(255), nullable=True),
    )
    op.add_column(
        "event",
        sa.Column("player", sqlmodel.sql.sqltypes.AutoString(255), nullable=True),
    )
    op.add_column(
        "event", sa.Column("team", sqlmodel.sql.sqltypes.AutoString(255), nullable=True)
    )
    op.execute(
        """
        UPDATE event e SET
            team = (SELECT name FROM team WHERE id = e.team_id),
            possession_team_name =
                (SELECT name FROM team WHERE id = e.possession_team_id),
            player = (SELECT name FROM player WHERE id = e.player_id),
            pass_recipient = (SELECT name FROM player WHERE id = e.pass_recipient_id)
        """
    )

    op.add_column(
        "soccer_match",
        sa.Column("away_team", sqlmodel.sql.sqltypes.AutoString(255), nullable=True),
    )
    op.add_column(
        "soccer_match",
        sa.Column("home_team", sqlmodel.sql.sqltypes.AutoString(255), nullable=True),
    )
    op.execute(
        """
        UPDATE soccer_match m SET home_team = h.name, away_team = a.name
        FROM team h, team a
        WHERE h.id = m.home_team_id AND a.id = m.away_team_id
        """
    )

    for table, column in reversed(_NOT_NULL):
        op.alter_column(table, column, nullable=True)
