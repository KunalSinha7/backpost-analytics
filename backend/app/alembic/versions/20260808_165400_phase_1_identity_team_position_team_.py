"""phase 1 identity: team, position, team_alias, entity FKs

Revision ID: 978091516b84
Revises: 87e2e9cbdd6e
Create Date: 2026-08-08 16:54:00.351942

Expand step of Phase 1 (§3). Adds the three new identity tables and hangs
nullable FK columns beside the existing string columns. Nothing reads the new
columns yet and nothing is dropped, so this migration is a pure no-op for
behaviour — the backfill that follows is what gives them values, and Phase 4
is what makes them NOT NULL.

Two departures from `alembic revision --autogenerate`, both deliberate:

1. **Every constraint is named explicitly.** Autogenerate emitted
   `op.create_foreign_key(None, ...)` paired with `op.drop_constraint(None, ...)`.
   The create works (Postgres assigns a default name), but the drop does not —
   there is no constraint named `None`, so `alembic downgrade` crashes on the
   first one. Naming them is what makes this migration reversible, which the
   phase gate requires.

2. **The UNIQUE constraints from §6/M4 are added here**, not left to a later
   phase. `UNIQUE(source_id, external_id)` is the constraint that makes the
   resolver's get-or-create safe under concurrency, and it is the structural
   reason the Marseille duplicate cannot come back: identity is the id pair, so
   two names cannot produce two rows. `UNIQUE(lineup.match_id,
   statsbomb_player_id)` closes M4's other hazard — today idempotency rests
   solely on `has_lineups_for_match`, so a half-failed lineup ingest is
   permanently stuck and silently skipped.

   Verified before adding: 0 duplicate (match_id, statsbomb_player_id) pairs.
   Note it is keyed on `statsbomb_player_id`, the column that is populated
   *now*, rather than the new `player_id` — a UNIQUE over all-NULL `player_id`
   would enforce nothing, since Postgres treats NULLs as distinct.
"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "978091516b84"
down_revision = "87e2e9cbdd6e"
branch_labels = None
depends_on = None


def upgrade():
    # --- new identity tables -------------------------------------------------
    op.create_table(
        "position",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column(
            "external_id", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False
        ),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["data_source.id"], name="fk_position_source_id_data_source"
        ),
        sa.PrimaryKeyConstraint("id", name="position_pkey"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_position_source_ext"),
    )
    op.create_index(op.f("ix_position_name"), "position", ["name"], unique=False)
    op.create_index(
        op.f("ix_position_source_id"), "position", ["source_id"], unique=False
    )

    op.create_table(
        "team",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column(
            "external_id", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False
        ),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("gender", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
        sa.Column(
            "country_name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["data_source.id"], name="fk_team_source_id_data_source"
        ),
        sa.PrimaryKeyConstraint("id", name="team_pkey"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_team_source_ext"),
    )
    op.create_index(op.f("ix_team_name"), "team", ["name"], unique=False)
    op.create_index(op.f("ix_team_source_id"), "team", ["source_id"], unique=False)

    op.create_table(
        "team_alias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["data_source.id"], name="fk_team_alias_source_id_data_source"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["team.id"], name="fk_team_alias_team_id_team"
        ),
        sa.PrimaryKeyConstraint("id", name="team_alias_pkey"),
        # Lets the resolver record aliases unconditionally and let the DB
        # deduplicate, instead of every caller checking first.
        sa.UniqueConstraint(
            "team_id", "source_id", "name", name="uq_team_alias_team_source_name"
        ),
    )
    op.create_index(op.f("ix_team_alias_name"), "team_alias", ["name"], unique=False)
    op.create_index(
        op.f("ix_team_alias_source_id"), "team_alias", ["source_id"], unique=False
    )
    op.create_index(
        op.f("ix_team_alias_team_id"), "team_alias", ["team_id"], unique=False
    )

    # --- event FKs -----------------------------------------------------------
    # No index on team_id/player_id here: §2.2 puts the composite
    # (player_id, match_id) / (team_id, match_id) indexes in Phase 3, and a
    # single-column index on the same leading column would be redundant.
    op.add_column("event", sa.Column("team_id", sa.Uuid(), nullable=True))
    op.add_column("event", sa.Column("possession_team_id", sa.Uuid(), nullable=True))
    op.add_column("event", sa.Column("player_id", sa.Uuid(), nullable=True))
    op.add_column("event", sa.Column("pass_recipient_id", sa.Uuid(), nullable=True))
    op.add_column("event", sa.Column("position_id", sa.Uuid(), nullable=True))
    op.add_column(
        "event", sa.Column("substitution_replacement_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key("fk_event_team_id_team", "event", "team", ["team_id"], ["id"])
    op.create_foreign_key(
        "fk_event_possession_team_id_team",
        "event",
        "team",
        ["possession_team_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_event_player_id_player", "event", "player", ["player_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_event_pass_recipient_id_player",
        "event",
        "player",
        ["pass_recipient_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_event_position_id_position", "event", "position", ["position_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_event_substitution_replacement_id_player",
        "event",
        "player",
        ["substitution_replacement_id"],
        ["id"],
    )

    # --- frame360 hard FK ----------------------------------------------------
    op.add_column("frame360", sa.Column("event_id", sa.Uuid(), nullable=True))
    op.create_unique_constraint("uq_frame360_event_id", "frame360", ["event_id"])
    op.create_foreign_key(
        "fk_frame360_event_id_event", "frame360", "event", ["event_id"], ["id"]
    )

    # --- lineup FKs ----------------------------------------------------------
    op.add_column("lineup", sa.Column("team_id", sa.Uuid(), nullable=True))
    op.add_column("lineup", sa.Column("player_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_lineup_player_id"), "lineup", ["player_id"], unique=False)
    op.create_index(op.f("ix_lineup_team_id"), "lineup", ["team_id"], unique=False)
    op.create_foreign_key(
        "fk_lineup_team_id_team", "lineup", "team", ["team_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_lineup_player_id_player", "lineup", "player", ["player_id"], ["id"]
    )
    op.create_unique_constraint(
        "uq_lineup_match_statsbomb_player", "lineup", ["match_id", "statsbomb_player_id"]
    )

    # --- player source columns -----------------------------------------------
    op.add_column("player", sa.Column("source_id", sa.Uuid(), nullable=True))
    op.add_column(
        "player",
        sa.Column(
            "external_id", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True
        ),
    )
    op.create_index(op.f("ix_player_source_id"), "player", ["source_id"], unique=False)
    op.create_foreign_key(
        "fk_player_source_id_data_source", "player", "data_source", ["source_id"], ["id"]
    )
    op.create_unique_constraint(
        "uq_player_source_ext", "player", ["source_id", "external_id"]
    )

    # --- soccer_match team FKs ----------------------------------------------
    # Indexed, unlike the event FKs: the optional `team_id` filter added to
    # /matches in this phase queries home_team_id/away_team_id directly.
    op.add_column("soccer_match", sa.Column("home_team_id", sa.Uuid(), nullable=True))
    op.add_column("soccer_match", sa.Column("away_team_id", sa.Uuid(), nullable=True))
    op.create_index(
        op.f("ix_soccer_match_home_team_id"),
        "soccer_match",
        ["home_team_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_soccer_match_away_team_id"),
        "soccer_match",
        ["away_team_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_soccer_match_home_team_id_team",
        "soccer_match",
        "team",
        ["home_team_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_soccer_match_away_team_id_team",
        "soccer_match",
        "team",
        ["away_team_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(
        "fk_soccer_match_away_team_id_team", "soccer_match", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_soccer_match_home_team_id_team", "soccer_match", type_="foreignkey"
    )
    op.drop_index(op.f("ix_soccer_match_away_team_id"), table_name="soccer_match")
    op.drop_index(op.f("ix_soccer_match_home_team_id"), table_name="soccer_match")
    op.drop_column("soccer_match", "away_team_id")
    op.drop_column("soccer_match", "home_team_id")

    op.drop_constraint("uq_player_source_ext", "player", type_="unique")
    op.drop_constraint("fk_player_source_id_data_source", "player", type_="foreignkey")
    op.drop_index(op.f("ix_player_source_id"), table_name="player")
    op.drop_column("player", "external_id")
    op.drop_column("player", "source_id")

    op.drop_constraint("uq_lineup_match_statsbomb_player", "lineup", type_="unique")
    op.drop_constraint("fk_lineup_player_id_player", "lineup", type_="foreignkey")
    op.drop_constraint("fk_lineup_team_id_team", "lineup", type_="foreignkey")
    op.drop_index(op.f("ix_lineup_team_id"), table_name="lineup")
    op.drop_index(op.f("ix_lineup_player_id"), table_name="lineup")
    op.drop_column("lineup", "player_id")
    op.drop_column("lineup", "team_id")

    op.drop_constraint("fk_frame360_event_id_event", "frame360", type_="foreignkey")
    op.drop_constraint("uq_frame360_event_id", "frame360", type_="unique")
    op.drop_column("frame360", "event_id")

    op.drop_constraint(
        "fk_event_substitution_replacement_id_player", "event", type_="foreignkey"
    )
    op.drop_constraint("fk_event_position_id_position", "event", type_="foreignkey")
    op.drop_constraint("fk_event_pass_recipient_id_player", "event", type_="foreignkey")
    op.drop_constraint("fk_event_player_id_player", "event", type_="foreignkey")
    op.drop_constraint("fk_event_possession_team_id_team", "event", type_="foreignkey")
    op.drop_constraint("fk_event_team_id_team", "event", type_="foreignkey")
    op.drop_column("event", "substitution_replacement_id")
    op.drop_column("event", "position_id")
    op.drop_column("event", "pass_recipient_id")
    op.drop_column("event", "player_id")
    op.drop_column("event", "possession_team_id")
    op.drop_column("event", "team_id")

    op.drop_index(op.f("ix_team_alias_team_id"), table_name="team_alias")
    op.drop_index(op.f("ix_team_alias_source_id"), table_name="team_alias")
    op.drop_index(op.f("ix_team_alias_name"), table_name="team_alias")
    op.drop_table("team_alias")

    op.drop_index(op.f("ix_team_source_id"), table_name="team")
    op.drop_index(op.f("ix_team_name"), table_name="team")
    op.drop_table("team")

    op.drop_index(op.f("ix_position_source_id"), table_name="position")
    op.drop_index(op.f("ix_position_name"), table_name="position")
    op.drop_table("position")
