"""add match_formation, match_formation_slot, shot_freeze_frame

Revision ID: 9122af629aa4
Revises: 2fe0be7dbfe0
Create Date: 2026-08-22 14:22:12.000000

Adds the two pieces of positional data issue #32 identifies as discarded at
parse time even though `event.raw_event` retains them in full — zero re-fetch
needed for either backfill:

1. **Tactics / formations.** 485 events (188 Starting XI, 297 Tactical Shift)
   carry a `tactics` object: `{"formation": 442, "lineup": [{"player": {...},
   "position": {...}, "jersey_number": N}, ...]}`. `match_formation` is one row
   per such event; `match_formation_slot` is one row per player in its lineup
   (11 per formation in source data).

2. **Shot freeze frames.** ~2,500 shot events carry `shot_freeze_frame`, an
   array of `{"location": [x, y], "player": {...}, "position": {...},
   "teammate": bool}` — the positions of every visible player at the moment of
   the shot. `frame360` holds 0 rows in the dev DB, so this is the only
   positional-context data actually present.

`position_id` on both new child tables reuses the `position` lookup table
introduced by Phase 1 (`978091516b84`) rather than defining a new one, keyed
the same way that table already is: `(source_id, external_id)` where
`external_id` is the StatsBomb position id as a string. `player_id` resolves
against `player.statsbomb_id`, mirroring `EntityResolver.resolve_player`.

**Hazards this backfill steps around (§6/B1 in the normalization plan):**

- `raw_event` is `json`, not `jsonb` — every operation below casts to
  `jsonb` first so `?` (key-exists) and `jsonb_array_elements` are usable.
- `raw_event->'field'` yields the JSON `null` literal (not SQL NULL) for a
  field that is present but null, so `NULLIF(x, 'null'::jsonb)` guards every
  optional lookup, matching `80647ecb6d8e`'s precedent.
- Nullable numeric ids get coerced to float64 by pandas before
  `model_dump()`, so a raw id can arrive as `"397683.0"`. Every id comparison
  here goes through `::numeric::bigint` rather than a bare `::int`/`::bigint`,
  even though the ids nested inside `tactics`/`shot_freeze_frame` (list/object
  columns, not flattened scalar columns) are not known to exhibit this — the
  cost of the extra cast is negligible and it costs nothing to be defensive
  here where it cannot be verified against the live DB from this environment.

**Player ids that don't resolve don't fail the migration.** Both child tables
have nullable `player_id`/`position_id` and are populated with `LEFT JOIN`s:
an unresolvable player leaves that one slot/frame-entry with a NULL
`player_id` rather than being dropped (which would break the "11 slots per
formation" invariant) or aborting the whole statement.

**`is_keeper` is derived, not a raw field.** StatsBomb's `shot_freeze_frame`
entries carry `location`, `player`, `position` and `teammate` — no `keeper`
key. `is_keeper` is computed as `position.id == 1` ("Goalkeeper"), the same
id the tactics payload's own example in the issue uses
(`{"id": 1, "name": "Goalkeeper"}`) and the same vocabulary `position.external_id`
already stores. This is a design decision, not a verified fact about every
row — flagged in the PR as something this environment could not check
against live data.

**Not verified from this environment** (no access to the 234k-event dev DB):
the exact row counts (485 formations / ~2,500 freeze-frame shots), whether
every formation ends up with exactly 11 slots, and whether the `is_keeper`
derivation above matches every row. The migration was verified to apply
cleanly on a fresh empty database, where every backfill INSERT is a no-op.
"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "9122af629aa4"
down_revision = "92a220acbd07"
branch_labels = None
depends_on = None


def upgrade():
    # --- schema ---------------------------------------------------------
    op.create_table(
        "match_formation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column(
            "formation", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column("from_period", sa.Integer(), nullable=False),
        sa.Column(
            "from_time", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["soccer_match.id"],
            name="fk_match_formation_match_id_soccer_match",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["team.id"], name="fk_match_formation_team_id_team"
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["event.id"], name="fk_match_formation_event_id_event"
        ),
        sa.PrimaryKeyConstraint("id", name="match_formation_pkey"),
        sa.UniqueConstraint("event_id", name="uq_match_formation_event_id"),
    )
    op.create_index(
        op.f("ix_match_formation_match_id"),
        "match_formation",
        ["match_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_match_formation_team_id"), "match_formation", ["team_id"], unique=False
    )

    op.create_table(
        "match_formation_slot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_formation_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=True),
        sa.Column("position_id", sa.Uuid(), nullable=True),
        sa.Column("jersey_number", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["match_formation_id"],
            ["match_formation.id"],
            name="fk_match_formation_slot_match_formation_id_match_formation",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["player.id"], name="fk_match_formation_slot_player_id_player"
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["position.id"],
            name="fk_match_formation_slot_position_id_position",
        ),
        sa.PrimaryKeyConstraint("id", name="match_formation_slot_pkey"),
    )
    op.create_index(
        op.f("ix_match_formation_slot_match_formation_id"),
        "match_formation_slot",
        ["match_formation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_match_formation_slot_player_id"),
        "match_formation_slot",
        ["player_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_match_formation_slot_position_id"),
        "match_formation_slot",
        ["position_id"],
        unique=False,
    )

    op.create_table(
        "shot_freeze_frame",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=True),
        sa.Column("position_id", sa.Uuid(), nullable=True),
        sa.Column("location_x", sa.Float(), nullable=True),
        sa.Column("location_y", sa.Float(), nullable=True),
        sa.Column("is_teammate", sa.Boolean(), nullable=False),
        sa.Column("is_keeper", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["event.id"], name="fk_shot_freeze_frame_event_id_event"
        ),
        sa.ForeignKeyConstraint(
            ["player_id"], ["player.id"], name="fk_shot_freeze_frame_player_id_player"
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["position.id"],
            name="fk_shot_freeze_frame_position_id_position",
        ),
        sa.PrimaryKeyConstraint("id", name="shot_freeze_frame_pkey"),
    )
    op.create_index(
        op.f("ix_shot_freeze_frame_event_id"),
        "shot_freeze_frame",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_shot_freeze_frame_player_id"),
        "shot_freeze_frame",
        ["player_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_shot_freeze_frame_position_id"),
        "shot_freeze_frame",
        ["position_id"],
        unique=False,
    )

    # --- backfill ---------------------------------------------------------
    bind = op.get_bind()

    # Extend the position vocabulary with any id this payload uses that the
    # main `position` backfill never saw, so match_formation_slot.position_id
    # and shot_freeze_frame.position_id resolve rather than staying NULL.
    # ON CONFLICT DO NOTHING mirrors EntityResolver.resolve_position's
    # get-or-create: a concurrent/prior writer may have already added the row.
    bind.execute(
        sa.text(
            """
            WITH raw_positions AS (
                SELECT
                    slot -> 'position' ->> 'id' AS ext_raw,
                    slot -> 'position' ->> 'name' AS pos_name
                FROM event e,
                    jsonb_array_elements(
                        NULLIF(e.raw_event::jsonb -> 'tactics' -> 'lineup', 'null'::jsonb)
                    ) AS slot
                WHERE e.type_name IN ('Starting XI', 'Tactical Shift')
                    AND slot -> 'position' ->> 'id' IS NOT NULL

                UNION ALL

                SELECT
                    ff -> 'position' ->> 'id' AS ext_raw,
                    ff -> 'position' ->> 'name' AS pos_name
                FROM event e,
                    jsonb_array_elements(
                        NULLIF(e.raw_event::jsonb -> 'shot_freeze_frame', 'null'::jsonb)
                    ) AS ff
                WHERE ff -> 'position' ->> 'id' IS NOT NULL
            ),
            distinct_positions AS (
                SELECT
                    (ext_raw::numeric::bigint)::text AS external_id,
                    max(pos_name) AS name
                FROM raw_positions
                GROUP BY (ext_raw::numeric::bigint)::text
            )
            INSERT INTO position (id, source_id, external_id, name)
            SELECT uuid_generate_v4(), ds.id, dp.external_id, dp.name
            FROM distinct_positions dp
            JOIN data_source ds ON ds.key = 'statsbomb'
            ON CONFLICT (source_id, external_id) DO NOTHING
            """
        )
    )

    # One match_formation per Starting XI / Tactical Shift event that carries
    # a non-null `tactics` object with a formation code.
    bind.execute(
        sa.text(
            """
            INSERT INTO match_formation
                (id, match_id, team_id, event_id, formation, from_period, from_time)
            SELECT
                uuid_generate_v4(),
                e.match_id,
                e.team_id,
                e.id,
                ((e.raw_event::jsonb -> 'tactics' ->> 'formation')::numeric::bigint)::text,
                e.period,
                e.timestamp
            FROM event e
            WHERE e.type_name IN ('Starting XI', 'Tactical Shift')
                AND NULLIF(e.raw_event::jsonb -> 'tactics', 'null'::jsonb) IS NOT NULL
                AND (e.raw_event::jsonb -> 'tactics' ->> 'formation') IS NOT NULL
            """
        )
    )

    # One match_formation_slot per player in the setting event's
    # tactics.lineup[]. LEFT JOINs on player/position: an id that doesn't
    # resolve leaves that column NULL on this slot rather than dropping the
    # slot (which would break "11 slots per formation") or the migration.
    bind.execute(
        sa.text(
            """
            INSERT INTO match_formation_slot
                (id, match_formation_id, player_id, position_id, jersey_number)
            SELECT
                uuid_generate_v4(),
                mf.id,
                p.id,
                pos.id,
                (slot ->> 'jersey_number')::numeric::bigint
            FROM match_formation mf
            JOIN event e ON e.id = mf.event_id
            CROSS JOIN LATERAL jsonb_array_elements(
                NULLIF(e.raw_event::jsonb -> 'tactics' -> 'lineup', 'null'::jsonb)
            ) AS slot
            LEFT JOIN player p
                ON p.statsbomb_id = (slot -> 'player' ->> 'id')::numeric::bigint
            LEFT JOIN data_source ds ON ds.key = 'statsbomb'
            LEFT JOIN position pos
                ON pos.source_id = ds.id
                AND pos.external_id
                    = ((slot -> 'position' ->> 'id')::numeric::bigint)::text
            """
        )
    )

    # One shot_freeze_frame row per visible player in a shot event's
    # shot_freeze_frame[]. Same LEFT JOIN policy as above.
    bind.execute(
        sa.text(
            """
            INSERT INTO shot_freeze_frame
                (id, event_id, player_id, position_id, location_x, location_y,
                 is_teammate, is_keeper)
            SELECT
                uuid_generate_v4(),
                e.id,
                p.id,
                pos.id,
                (ff -> 'location' ->> 0)::float,
                (ff -> 'location' ->> 1)::float,
                COALESCE((ff ->> 'teammate')::boolean, false),
                COALESCE(
                    ((ff -> 'position' ->> 'id')::numeric::bigint) = 1, false
                )
            FROM event e
            CROSS JOIN LATERAL jsonb_array_elements(
                NULLIF(e.raw_event::jsonb -> 'shot_freeze_frame', 'null'::jsonb)
            ) AS ff
            LEFT JOIN player p
                ON p.statsbomb_id = (ff -> 'player' ->> 'id')::numeric::bigint
            LEFT JOIN data_source ds ON ds.key = 'statsbomb'
            LEFT JOIN position pos
                ON pos.source_id = ds.id
                AND pos.external_id
                    = ((ff -> 'position' ->> 'id')::numeric::bigint)::text
            """
        )
    )


def downgrade():
    op.drop_index(op.f("ix_shot_freeze_frame_position_id"), table_name="shot_freeze_frame")
    op.drop_index(op.f("ix_shot_freeze_frame_player_id"), table_name="shot_freeze_frame")
    op.drop_index(op.f("ix_shot_freeze_frame_event_id"), table_name="shot_freeze_frame")
    op.drop_table("shot_freeze_frame")

    op.drop_index(
        op.f("ix_match_formation_slot_position_id"), table_name="match_formation_slot"
    )
    op.drop_index(
        op.f("ix_match_formation_slot_player_id"), table_name="match_formation_slot"
    )
    op.drop_index(
        op.f("ix_match_formation_slot_match_formation_id"),
        table_name="match_formation_slot",
    )
    op.drop_table("match_formation_slot")

    op.drop_index(op.f("ix_match_formation_team_id"), table_name="match_formation")
    op.drop_index(op.f("ix_match_formation_match_id"), table_name="match_formation")
    op.drop_table("match_formation")

    # Positions inserted by this migration's upgrade() are intentionally left
    # in place: they are indistinguishable from rows the Phase 1 backfill
    # would have created for the same (source_id, external_id), and downgrade
    # is a schema rollback, not a data rollback.
