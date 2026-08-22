"""add event_relation and key_pass/assisted_shot self-FKs on event

Revision ID: dc917ca9d4d3
Revises: 2fe0be7dbfe0
Create Date: 2026-08-22 14:19:18.000000

Normalizes the StatsBomb event graph that today lives only inside
`event.raw_event`, per issue #31:

- `event_relation(event_id, related_event_id)` from `raw_event->'related_events'`.
- `event.key_pass_event_id` from `raw_event->>'shot_key_pass_id'`.
- `event.assisted_shot_event_id` from `raw_event->>'pass_assisted_shot_id'`.

**Head caveat**: this branches off `2fe0be7dbfe0` alongside at least two
sibling migrations developed in parallel on separate branches (issue #30 and
others). Whichever of those lands first on `master` will need this file's
`down_revision` (and the PR) rebased onto the new head — there is nothing to
reconcile in the schema itself, just the revision chain.

**Directionality decision — store both directions, not canonical + UNION.**
`related_events` is symmetric in the source: a pass and its ball receipt each
list the other. Two ways to store that:

1. One row per literal array entry, both directions present as independent
   rows (chosen here).
2. Canonicalise to a single direction (e.g. only insert where
   `event_id < related_event_id`) and require a `UNION` of both column
   orientations at read time to answer "what's related to event X".

(1) wins for three reasons:
- It is what the source data literally is. `related_events` is not a
  half-specified relation the app is choosing to complete symmetrically; both
  entries already exist in the feed. Storing one direction and reconstructing
  the other is extra logic to recover data that was never actually missing.
- The issue's own gate — "edge count matches ~546,468" — is a count of literal
  `related_events` array entries across all events, not a count of distinct
  unordered pairs. Canonicalising would produce roughly half that number
  (~273K) and the gate would need reinterpreting; storing both directions
  makes the gate check a literal, unambiguous equality.
- Every future query is `WHERE event_id = :id`, hitting the composite primary
  key's leading column directly. No UNION, no "try both columns" branch in
  application code, no risk of a query that checks only one side and quietly
  misses half the graph.
- The cost is a second index (`related_event_id`) and roughly 2x the row count
  of the canonical form — on the order of 1.1M rows of two UUIDs each, which
  is small next to the 376K-row `event` table itself.

**Backfill is a single in-database SQL pass, not a Python loop.** All three
source fields (`related_events`, `shot_key_pass_id`, `pass_assisted_shot_id`)
already live in `raw_event`, and every id they reference is a StatsBomb event
UUID already stored in the UNIQUE `event.statsbomb_id` column — so resolving
"UUID string -> this database's `event.id`" is a plain self-join on a column
that already has a unique index, no re-fetch required.

**Why the float-string cast hazard (nullable numeric ids pandas coerced to
float64, e.g. `"7626.0"`, breaking a bare `::int` cast) does not apply here**:
every value this migration reads — each `related_events` entry, and
`shot_key_pass_id` / `pass_assisted_shot_id` themselves — is a StatsBomb event
UUID *string*, never one of the numeric StatsBomb ids (player_id, team_id,
...) that went through that float64 round-trip. Every comparison below is
plain text equality against `event.statsbomb_id`; nothing is cast to a numeric
type.

**`raw_event` is `json`, not `jsonb`** (see `add_event_table` /
`add_data_source_raw_columns...`, where new JSON columns were deliberately
given `jsonb` and `raw_event` was left as-is). `json_array_elements_text` is
used throughout rather than the `jsonb_` variant, since there is no implicit
cast between the two types.

**Guarding the array extraction**: `raw_event -> 'related_events'` is SQL NULL
for the ~3% of events with no related events at all, but a `CASE` still wraps
it before it reaches `json_array_elements_text` — a *literal* JSON `null`
(present key, `null` value, distinct from an absent key) would otherwise make
that call raise "cannot extract elements from a scalar", since a filtering
`WHERE` clause after a `LATERAL` join does not stop the lateral function from
being invoked first.

**No hard gate assertion on the exact edge count in this migration.** The
546,468 figure was measured against the live dev DB, which this migration
cannot see (worktree has no access to it — see PR body). Hard-coding that
number here would make the migration fail the moment the dev DB's event count
changes at all. Instead this prints a diagnostic comparing edges inserted
against raw source entries, so a mismatch is visible in migration output
without turning a data-quality question into a failed deploy.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "dc917ca9d4d3"
down_revision = "2fe0be7dbfe0"
branch_labels = None
depends_on = None

# Extracted once so the INSERT and the diagnostic COUNT can't drift apart.
_RELATED_EVENTS_ARRAY = """
    CASE
        WHEN json_typeof(e.raw_event -> 'related_events') = 'array'
        THEN e.raw_event -> 'related_events'
        ELSE '[]'::json
    END
"""


def upgrade():
    bind = op.get_bind()

    # --- event_relation: the M:N join table ---------------------------------
    op.create_table(
        "event_relation",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("related_event_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["event.id"],
            name="fk_event_relation_event_id_event",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["related_event_id"],
            ["event.id"],
            name="fk_event_relation_related_event_id_event",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "event_id", "related_event_id", name="event_relation_pkey"
        ),
    )
    # Not strictly required by any query today (both directions are stored, so
    # "related to X" is always `WHERE event_id = X`, served by the primary
    # key's leading column) — this covers FK-integrity checks on `event`
    # deletes, which would otherwise sequential-scan this table.
    op.create_index(
        "ix_event_relation_related_event_id",
        "event_relation",
        ["related_event_id"],
    )

    # --- event: nullable self-FKs for assist attribution --------------------
    op.add_column("event", sa.Column("key_pass_event_id", sa.Uuid(), nullable=True))
    op.add_column(
        "event", sa.Column("assisted_shot_event_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_event_key_pass_event_id_event",
        "event",
        "event",
        ["key_pass_event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_event_assisted_shot_event_id_event",
        "event",
        "event",
        ["assisted_shot_event_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- backfill: related_events -> event_relation (both directions) -------
    # The FK constraints above are already live, so any candidate edge that
    # fails to resolve to a real `event.id` is excluded by the JOIN rather
    # than inserted and rejected — "no orphans" (the issue's gate) holds by
    # construction, not by a follow-up check.
    insert_result = bind.execute(
        sa.text(
            f"""
            INSERT INTO event_relation (event_id, related_event_id)
            SELECT DISTINCT e.id, re.id
            FROM event e
            CROSS JOIN LATERAL json_array_elements_text({_RELATED_EVENTS_ARRAY})
                AS rel(related_statsbomb_id)
            JOIN event re ON re.statsbomb_id = rel.related_statsbomb_id
            ON CONFLICT DO NOTHING
            """
        )
    )
    edges_inserted = insert_result.rowcount

    source_entries = bind.execute(
        sa.text(
            f"""
            SELECT count(*)
            FROM event e
            CROSS JOIN LATERAL json_array_elements_text({_RELATED_EVENTS_ARRAY})
                AS rel(related_statsbomb_id)
            """
        )
    ).scalar_one()

    if source_entries:
        unresolved = source_entries - edges_inserted
        print(
            f"event_relation backfill: {edges_inserted} edges inserted from "
            f"{source_entries} raw `related_events` entries "
            f"({unresolved} did not resolve to a known event.statsbomb_id or "
            "were duplicates within one event's own list). Compare "
            "`edges_inserted` against the current source count as the "
            "issue's gate requires; a nonzero `unresolved` on real data is a "
            "data-quality signal worth investigating, not a migration "
            "failure."
        )

    # --- backfill: shot_key_pass_id / pass_assisted_shot_id -----------------
    bind.execute(
        sa.text(
            """
            UPDATE event e
            SET key_pass_event_id = kp.id
            FROM event kp
            WHERE kp.statsbomb_id = e.raw_event ->> 'shot_key_pass_id'
              AND e.raw_event ->> 'shot_key_pass_id' IS NOT NULL
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE event e
            SET assisted_shot_event_id = asis.id
            FROM event asis
            WHERE asis.statsbomb_id = e.raw_event ->> 'pass_assisted_shot_id'
              AND e.raw_event ->> 'pass_assisted_shot_id' IS NOT NULL
            """
        )
    )


def downgrade():
    op.drop_constraint(
        "fk_event_assisted_shot_event_id_event", "event", type_="foreignkey"
    )
    op.drop_constraint("fk_event_key_pass_event_id_event", "event", type_="foreignkey")
    op.drop_column("event", "assisted_shot_event_id")
    op.drop_column("event", "key_pass_event_id")
    op.drop_index("ix_event_relation_related_event_id", table_name="event_relation")
    op.drop_table("event_relation")
