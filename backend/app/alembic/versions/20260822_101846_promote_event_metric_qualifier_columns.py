"""promote event metric/qualifier columns from raw_event (issue #33)

Revision ID: 9f3f8d81b1e1
Revises: 2fe0be7dbfe0
Create Date: 2026-08-22 10:18:46.505088

Promotes scalar metric/qualifier fields that live only inside `event.raw_event`
into real columns: the headline `shot_statsbomb_xg` (expected goals), pass
geometry (`pass_length`/`pass_angle`), disciplinary cards, and the low-
cardinality qualifier strings/booleans (pass/shot/duel/dribble/goalkeeper
outcome-and-type fields, plus boolean flags like `counterpress`,
`pass_cross`, `shot_first_time`, ...).

**Deliberately no lookup tables.** Each qualifier is 3-8 distinct values; a
join on a 376k-row hot path costs more than the storage saves. Same call the
existing schema already makes for `event.type_name` / `play_pattern_name`.

**Zero re-fetch.** Every field here is already present in `event.raw_event`
(an `extra="allow"` pydantic dump, so nothing the StatsBomb feed sent was
ever dropped) — the backfill is a pure in-database UPDATE, no re-ingest.

## json -> jsonb

`event.raw_event` was still Postgres `json` (see the 20260622 add_event_table
and 20260806 add_data_source_raw_columns migrations — `sa.JSON()`/`JSON()`,
never converted). This migration converts it to `jsonb` as part of the same
pass, because:

- The backfill below already requires a full rewrite of all ~376k rows (an
  UPDATE touching every row rewrites every page regardless of column count),
  so folding the type change into the same migration avoids paying that cost
  twice.
- `jsonb` supports the containment/path operators issues #31 and #32 need
  (e.g. `jsonb_array_elements_text` on `related_events`), and there is no
  reason for a column added this recently to keep the slower text-based json
  representation.

**Cost, stated plainly:** `ALTER TABLE event ALTER COLUMN raw_event TYPE
jsonb USING raw_event::jsonb` cannot be done in-place — json and jsonb have
different on-disk representations, so Postgres must rewrite every row of the
table, holding an ACCESS EXCLUSIVE lock (blocking all reads and writes on
`event`) for the duration. On the real ~376k-row dev database this is a
several-second-to-low-tens-of-seconds outage window on `event`, not
instantaneous — schedule the deploy accordingly. It was NOT measured against
the real dataset from this worktree (see PR description).

**Collision risk:** issues #31 and #32 are sibling migrations off the same
`down_revision` (`2fe0be7dbfe0`) and may also perform this same conversion
independently. Whichever merges first should keep its conversion; whichever
merges second must drop its own duplicate `ALTER COLUMN ... TYPE jsonb` during
rebase (re-running it against an already-jsonb column is harmless but
redundant work on a large table).

## The float-string cast hazard

Nullable numeric ids/metrics were coerced to float64 by pandas before
`model_dump()`, so e.g. `raw_event->>'player_id'` is the text `"7626.0"` and a
bare `::int` cast throws. None of the columns added here are integer ids, but
the same family of value (`shot_statsbomb_xg`, `pass_length`, `pass_angle`)
is cast via `::double precision`, which — unlike `::int` — accepts a decimal
point natively, so this particular hazard does not apply to them. It is
recorded here because it is the reason this migration exists at all (§1.5 of
database-normalization.md), not because these specific casts trip it.

## Gate — NOT verified in this environment

This worktree has no access to the real 376,362-row dev database. The
following, called out in issue #33, could NOT be checked here and must be
verified post-deploy:

- `shot_statsbomb_xg` present on exactly 2,536 shot events, mean ~0.115
- Column count parity against the full source key inventory (the boolean
  qualifier list in particular was reconstructed from public StatsBomb
  open-data schema knowledge, not from a `jsonb_object_keys(raw_event)` query
  against real data — treat it as a best-effort superset, not a verified
  exact match)

What IS enforced here, and holds on any dataset including an empty one: no
non-shot event may have a non-null `shot_statsbomb_xg` (see
`_assert_xg_is_shot_only` below).
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9f3f8d81b1e1"
down_revision = "9122af629aa4"
branch_labels = None
depends_on = None


# (column, raw_event key) — identical names except where noted; kept as pairs
# so a future rename doesn't have to touch every list below.
_FLOAT_METRICS = [
    ("shot_statsbomb_xg", "shot_statsbomb_xg"),
    ("pass_length", "pass_length"),
    ("pass_angle", "pass_angle"),
]

# (column, max_length) — cards and qualifier strings, all low-cardinality.
_STRING_QUALIFIERS = [
    ("foul_committed_card", 50),
    ("bad_behaviour_card", 50),
    ("pass_height", 50),
    ("pass_body_part", 50),
    ("pass_outcome", 50),
    ("pass_type", 50),
    ("pass_technique", 50),
    ("shot_outcome", 50),
    ("shot_body_part", 50),
    ("shot_technique", 50),
    ("shot_type", 50),
    ("duel_type", 50),
    ("duel_outcome", 50),
    ("dribble_outcome", 50),
    ("ball_receipt_outcome", 50),
    ("interception_outcome", 50),
    ("goalkeeper_type", 50),
    ("goalkeeper_outcome", 50),
    ("goalkeeper_position", 50),
    ("goalkeeper_technique", 50),
    ("goalkeeper_body_part", 50),
]

_BOOL_QUALIFIERS = [
    "counterpress",
    "pass_cross",
    "pass_switch",
    "pass_through_ball",
    "pass_goal_assist",
    "pass_shot_assist",
    "pass_cut_back",
    "pass_deflected",
    "pass_no_touch",
    "pass_miscommunication",
    "shot_first_time",
    "shot_one_on_one",
    "shot_open_goal",
    "shot_deflected",
    "shot_redirect",
    "shot_saved_off_target",
    "shot_saved_to_post",
    "shot_follows_dribble",
    "dribble_nutmeg",
    "dribble_overrun",
    "dribble_no_touch",
    "foul_committed_advantage",
    "foul_committed_penalty",
    "foul_won_advantage",
    "foul_won_defensive",
    "foul_won_penalty",
]


def _assert_xg_is_shot_only(bind) -> None:
    """General invariant, holds on any dataset (including an empty one)."""
    count = bind.execute(
        sa.text(
            "SELECT count(*) FROM event "
            "WHERE shot_statsbomb_xg IS NOT NULL AND type_name <> 'Shot'"
        )
    ).scalar_one()
    if count:
        raise RuntimeError(
            f"{count} non-Shot event(s) have a non-null shot_statsbomb_xg after "
            "backfill — the raw_event key mapping is wrong."
        )


def upgrade():
    bind = op.get_bind()

    # --- json -> jsonb -------------------------------------------------
    # Full-table rewrite, ACCESS EXCLUSIVE lock for the duration. See the
    # module docstring for the cost and the sibling-migration collision risk.
    op.execute("ALTER TABLE event ALTER COLUMN raw_event TYPE jsonb USING raw_event::jsonb")

    # --- add columns -----------------------------------------------------
    for column, _ in _FLOAT_METRICS:
        op.add_column("event", sa.Column(column, sa.Float(), nullable=True))
    for column, max_length in _STRING_QUALIFIERS:
        op.add_column(
            "event", sa.Column(column, sa.String(length=max_length), nullable=True)
        )
    for column in _BOOL_QUALIFIERS:
        op.add_column("event", sa.Column(column, sa.Boolean(), nullable=True))

    # --- backfill, one UPDATE pass ---------------------------------------
    # Zero re-fetch: every value is already in raw_event. A single UPDATE
    # touching every new column avoids rewriting the table once per column —
    # an UPDATE rewrites the pages it touches regardless of how many columns
    # in the row changed, so batching all of them here is strictly cheaper
    # than 48 separate single-column passes.
    set_clauses = [f"{c} = (raw_event->>'{k}')::double precision" for c, k in _FLOAT_METRICS]
    set_clauses += [f"{c} = raw_event->>'{c}'" for c, _ in _STRING_QUALIFIERS]
    set_clauses += [f"{c} = (raw_event->>'{c}')::boolean" for c in _BOOL_QUALIFIERS]
    op.execute("UPDATE event SET " + ", ".join(set_clauses))  # noqa: S608

    _assert_xg_is_shot_only(bind)


def downgrade():
    for column in _BOOL_QUALIFIERS:
        op.drop_column("event", column)
    for column, _ in _STRING_QUALIFIERS:
        op.drop_column("event", column)
    for column, _ in _FLOAT_METRICS:
        op.drop_column("event", column)

    # Reverse the json -> jsonb conversion. Also a full-table rewrite.
    op.execute("ALTER TABLE event ALTER COLUMN raw_event TYPE json USING raw_event::json")
