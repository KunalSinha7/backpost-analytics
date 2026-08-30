"""`match_formation` and its child `match_formation_slot`.

Both are projections of the `tactics` payload on Starting XI / Tactical Shift
events, so they are populated by running the extraction rather than by
inserting model instances. The child slots live here with their parent, the
same way `LineupPosition` has no repository of its own.
"""

import uuid

from sqlalchemy import text
from sqlmodel import Session

# One row per Starting XI / Tactical Shift event carrying a tactics payload.
# `event_id` is UNIQUE, which is what makes ON CONFLICT enough here.
_POPULATE_FORMATIONS_SQL = """
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

# LEFT JOINs on player/position are deliberate: an id that does not resolve
# leaves that column NULL rather than dropping the slot, which would silently
# break the "11 slots per formation" invariant. Guarded on "this formation has
# no slots yet" so a re-run cannot duplicate them.
_POPULATE_SLOTS_SQL = """
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


class MatchFormationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def populate_for_match(self, match_id: uuid.UUID) -> None:
        """Insert the formations and their slots for one match.

        Idempotent. The slot statement depends on the formations inserted
        immediately above it, so the order here is load-bearing.
        """
        self.session.execute(text(_POPULATE_FORMATIONS_SQL), {"match_id": match_id})
        self.session.execute(text(_POPULATE_SLOTS_SQL), {"match_id": match_id})
