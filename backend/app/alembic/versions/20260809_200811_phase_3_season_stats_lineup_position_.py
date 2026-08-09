"""phase 3 season stats: lineup_position and per-player indexes

Revision ID: 11e2f338bb26
Revises: 51e565e16027
Create Date: 2026-08-09 20:08:11.999416

Adds `lineup_position` — one row per stint a player spent on the pitch — and
the two composite indexes §2.2 specifies for the season-stats query.

`lineup.positions[]` was a repeating group inside a JSON column, which is a 1NF
violation and the direct reason per-90 stats were impossible: minutes played
lives inside that array and nothing could aggregate it.

The FK columns this indexes were deliberately left unindexed in Phase 1
(`978091516b84`) precisely so these composites could be created here instead.
A single-column index on `player_id` would be redundant with
`(player_id, match_id)` — same leading column — and would have to be dropped
again.
"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "11e2f338bb26"
down_revision = "51e565e16027"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lineup_position",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lineup_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("from_period", sa.Integer(), nullable=False),
        sa.Column("to_period", sa.Integer(), nullable=False),
        sa.Column("from_seconds", sa.Integer(), nullable=False),
        sa.Column("to_seconds", sa.Integer(), nullable=False),
        sa.Column(
            "start_reason", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False
        ),
        sa.Column(
            "end_reason", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["lineup_id"], ["lineup.id"], name="fk_lineup_position_lineup_id_lineup"
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["position.id"],
            name="fk_lineup_position_position_id_position",
        ),
        sa.PrimaryKeyConstraint("id", name="lineup_position_pkey"),
    )
    op.create_index(
        op.f("ix_lineup_position_lineup_id"),
        "lineup_position",
        ["lineup_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lineup_position_position_id"),
        "lineup_position",
        ["position_id"],
        unique=False,
    )

    # §2.2's season-stats indexes. Composite and in this order because the query
    # is "everything this player did, narrowed to the matches of one season":
    # player_id selects, match_id joins.
    op.create_index("ix_event_player_match", "event", ["player_id", "match_id"])
    op.create_index("ix_event_team_match", "event", ["team_id", "match_id"])


def downgrade():
    op.drop_index("ix_event_team_match", table_name="event")
    op.drop_index("ix_event_player_match", table_name="event")
    op.drop_index(op.f("ix_lineup_position_position_id"), table_name="lineup_position")
    op.drop_index(op.f("ix_lineup_position_lineup_id"), table_name="lineup_position")
    op.drop_table("lineup_position")
