"""Derivation of event-graph tables from `event.raw_event`.

`event_relation`, `match_formation`/`match_formation_slot` and
`shot_freeze_frame` are all projections of data that already lives in
`event.raw_event`. Issues #31 and #32 shipped them as one-off migration
backfills, which populated existing rows but left the ingest path untouched —
so on any freshly-ingested database the three tables stayed empty even though
the source JSON was present.

This module holds that same extraction as SQL, scoped to a single match, so
the ingest path can run it per match and produce results identical to the
migration backfill. Keeping one copy of the SQL is the point: a Python
reimplementation would be a second definition of "what these tables mean" and
would drift.

Every statement is idempotent, so re-running an ingest over already-ingested
matches repairs missing derived rows rather than duplicating them.
"""

import uuid

from sqlalchemy import text
from sqlmodel import Session

# `related_events` entries are StatsBomb event UUID strings, and the referenced
# events are always within the same match, so the self-join is match-scoped.
# ON CONFLICT covers the composite primary key (event_id, related_event_id).
_EVENT_RELATION_SQL = """
    INSERT INTO event_relation (event_id, related_event_id)
    SELECT e.id, r.id
    FROM event e
    CROSS JOIN LATERAL jsonb_array_elements_text(
        CASE
            WHEN jsonb_typeof(e.raw_event -> 'related_events') = 'array'
            THEN e.raw_event -> 'related_events'
            ELSE '[]'::jsonb
        END
    ) AS rel(statsbomb_id)
    JOIN event r ON r.statsbomb_id = rel.statsbomb_id
    WHERE e.match_id = :match_id
    ON CONFLICT DO NOTHING
"""

# Assist attribution: both columns point at another event in the same match.
# Guarded on IS NULL so a re-run is a no-op rather than a rewrite.
_KEY_PASS_SQL = """
    UPDATE event e
    SET key_pass_event_id = kp.id
    FROM event kp
    WHERE e.match_id = :match_id
      AND e.key_pass_event_id IS NULL
      AND e.raw_event ->> 'shot_key_pass_id' IS NOT NULL
      AND kp.statsbomb_id = e.raw_event ->> 'shot_key_pass_id'
"""

_ASSISTED_SHOT_SQL = """
    UPDATE event e
    SET assisted_shot_event_id = asis.id
    FROM event asis
    WHERE e.match_id = :match_id
      AND e.assisted_shot_event_id IS NULL
      AND e.raw_event ->> 'pass_assisted_shot_id' IS NOT NULL
      AND asis.statsbomb_id = e.raw_event ->> 'pass_assisted_shot_id'
"""

# One row per Starting XI / Tactical Shift event carrying a tactics payload.
# `event_id` is UNIQUE, so ON CONFLICT makes this idempotent.
_MATCH_FORMATION_SQL = """
    INSERT INTO match_formation
        (id, match_id, team_id, event_id, formation, from_period, from_time)
    SELECT
        gen_random_uuid(),
        e.match_id,
        e.team_id,
        e.id,
        ((e.raw_event -> 'tactics' ->> 'formation')::numeric::bigint)::text,
        e.period,
        e.timestamp
    FROM event e
    WHERE e.match_id = :match_id
      AND e.type_name IN ('Starting XI', 'Tactical Shift')
      AND NULLIF(e.raw_event -> 'tactics', 'null'::jsonb) IS NOT NULL
      AND (e.raw_event -> 'tactics' ->> 'formation') IS NOT NULL
    ON CONFLICT (event_id) DO NOTHING
"""

# LEFT JOINs on player/position mirror the migration: an id that does not
# resolve leaves the column NULL rather than dropping the slot, which would
# break the "11 slots per formation" invariant. Guarded on "no slots yet" so a
# re-run does not duplicate them.
_MATCH_FORMATION_SLOT_SQL = """
    INSERT INTO match_formation_slot
        (id, match_formation_id, player_id, position_id, jersey_number)
    SELECT
        gen_random_uuid(),
        mf.id,
        p.id,
        pos.id,
        (slot ->> 'jersey_number')::numeric::bigint
    FROM match_formation mf
    JOIN event e ON e.id = mf.event_id
    CROSS JOIN LATERAL jsonb_array_elements(
        NULLIF(e.raw_event -> 'tactics' -> 'lineup', 'null'::jsonb)
    ) AS slot
    LEFT JOIN player p
        ON p.statsbomb_id = (slot -> 'player' ->> 'id')::numeric::bigint
    LEFT JOIN data_source ds ON ds.key = 'statsbomb'
    LEFT JOIN position pos
        ON pos.source_id = ds.id
        AND pos.external_id = ((slot -> 'position' ->> 'id')::numeric::bigint)::text
    WHERE mf.match_id = :match_id
      AND NOT EXISTS (
          SELECT 1 FROM match_formation_slot s WHERE s.match_formation_id = mf.id
      )
"""

# One row per visible player in a shot's freeze frame. `is_keeper` is derived
# as position.id == 1 ("Goalkeeper"), matching the migration — StatsBomb does
# not ship an explicit keeper flag here.
_SHOT_FREEZE_FRAME_SQL = """
    INSERT INTO shot_freeze_frame
        (id, event_id, player_id, position_id, location_x, location_y,
         is_teammate, is_keeper)
    SELECT
        gen_random_uuid(),
        e.id,
        p.id,
        pos.id,
        (ff -> 'location' ->> 0)::float,
        (ff -> 'location' ->> 1)::float,
        COALESCE((ff ->> 'teammate')::boolean, false),
        COALESCE(((ff -> 'position' ->> 'id')::numeric::bigint) = 1, false)
    FROM event e
    CROSS JOIN LATERAL jsonb_array_elements(
        NULLIF(e.raw_event -> 'shot_freeze_frame', 'null'::jsonb)
    ) AS ff
    LEFT JOIN player p
        ON p.statsbomb_id = (ff -> 'player' ->> 'id')::numeric::bigint
    LEFT JOIN data_source ds ON ds.key = 'statsbomb'
    LEFT JOIN position pos
        ON pos.source_id = ds.id
        AND pos.external_id = ((ff -> 'position' ->> 'id')::numeric::bigint)::text
    WHERE e.match_id = :match_id
      AND NOT EXISTS (
          SELECT 1 FROM shot_freeze_frame f WHERE f.event_id = e.id
      )
"""

_STATEMENTS = (
    _EVENT_RELATION_SQL,
    _KEY_PASS_SQL,
    _ASSISTED_SHOT_SQL,
    _MATCH_FORMATION_SQL,
    _MATCH_FORMATION_SLOT_SQL,
    _SHOT_FREEZE_FRAME_SQL,
)


class DerivationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def derive_for_match(self, match_id: uuid.UUID) -> None:
        """Populate the derived event-graph tables for one match.

        Idempotent: safe to call on a match whose derived rows already exist.
        Ordering matters only in that formation slots depend on the formations
        inserted immediately above them.
        """
        for statement in _STATEMENTS:
            self.session.execute(text(statement), {"match_id": match_id})
