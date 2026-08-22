"""add referee, stadium, manager, competition_stage entities

Revision ID: 92a220acbd07
Revises: 2fe0be7dbfe0
Create Date: 2026-08-22 12:00:00.000000

Implements issue #30 — a decision record that explicitly recommended
*deferring* this work ("No analytics use case today. Promoting them now
would be speculative"). It is implemented here at the repo owner's request;
see the PR description for that context.

Pure "expand" migration, the same shape as Phase 1 (§3) for team/position:
four new identity tables plus nullable FK columns hung beside the existing
free-text columns on `soccer_match` (`referee`, `stadium`,
`home_manager_name`, `away_manager_name`, `competition_stage_name`), which
this migration does not touch. Nothing reads the new columns yet, so this is
a no-op for behaviour — a separate backfill
(`MatchService.backfill_deferred_entities`) is what gives them values, and
this migration does not attempt one itself: it cannot reach the network to
re-fetch `sb.matches()`, and there is no existing data in this repository to
backfill against (see the PR's "not verified" section).

One `Manager` table serves both `home_manager_id` and `away_manager_id` —
they are two FKs to the same entity, not two entities, matching how a single
`Team` table already serves `home_team_id` / `away_team_id`.

Every constraint is named explicitly (not left to autogenerate's `None`),
for the same reason Phase 1 did it: an unnamed constraint cannot be dropped
by name in `downgrade`.
"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "92a220acbd07"
down_revision = "2fe0be7dbfe0"
branch_labels = None
depends_on = None

# (table, name_length) for the four new identity tables — all share the same
# source_id/external_id/name shape as `team` / `position`.
_NEW_TABLES = [
    ("referee", 255),
    ("stadium", 255),
    ("manager", 255),
    ("competition_stage", 100),
]

# (soccer_match column, target table) for the five new nullable FKs.
_NEW_MATCH_FKS = [
    ("referee_id", "referee"),
    ("stadium_id", "stadium"),
    ("home_manager_id", "manager"),
    ("away_manager_id", "manager"),
    ("competition_stage_id", "competition_stage"),
]


def upgrade():
    for table, name_length in _NEW_TABLES:
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("source_id", sa.Uuid(), nullable=False),
            sa.Column(
                "external_id",
                sqlmodel.sql.sqltypes.AutoString(length=64),
                nullable=False,
            ),
            sa.Column(
                "name",
                sqlmodel.sql.sqltypes.AutoString(length=name_length),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["source_id"],
                ["data_source.id"],
                name=f"fk_{table}_source_id_data_source",
            ),
            sa.PrimaryKeyConstraint("id", name=f"{table}_pkey"),
            sa.UniqueConstraint(
                "source_id", "external_id", name=f"uq_{table}_source_ext"
            ),
        )
        op.create_index(op.f(f"ix_{table}_name"), table, ["name"], unique=False)
        op.create_index(
            op.f(f"ix_{table}_source_id"), table, ["source_id"], unique=False
        )

    for column, target_table in _NEW_MATCH_FKS:
        op.add_column("soccer_match", sa.Column(column, sa.Uuid(), nullable=True))
        op.create_index(
            op.f(f"ix_soccer_match_{column}"),
            "soccer_match",
            [column],
            unique=False,
        )
        op.create_foreign_key(
            f"fk_soccer_match_{column}_{target_table}",
            "soccer_match",
            target_table,
            [column],
            ["id"],
        )


def downgrade():
    for column, target_table in reversed(_NEW_MATCH_FKS):
        op.drop_constraint(
            f"fk_soccer_match_{column}_{target_table}",
            "soccer_match",
            type_="foreignkey",
        )
        op.drop_index(op.f(f"ix_soccer_match_{column}"), table_name="soccer_match")
        op.drop_column("soccer_match", column)

    for table, _name_length in reversed(_NEW_TABLES):
        op.drop_index(op.f(f"ix_{table}_source_id"), table_name=table)
        op.drop_index(op.f(f"ix_{table}_name"), table_name=table)
        op.drop_table(table)
