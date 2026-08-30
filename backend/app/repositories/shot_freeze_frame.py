"""`shot_freeze_frame` — player positions at the moment of a shot.

A projection of the `shot_freeze_frame` payload on shot events, so it is
populated by running the extraction rather than by inserting model instances.
"""

import uuid

from sqlalchemy import text
from sqlmodel import Session

# One row per visible player in a shot's freeze frame. `is_keeper` is derived
# as position.id == 1 ("Goalkeeper") — StatsBomb ships no explicit keeper flag
# here. Same LEFT JOIN policy as the formation slots: an unresolved id leaves
# the column NULL rather than dropping the row.
_POPULATE_SQL = """
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


class ShotFreezeFrameRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def populate_for_match(self, match_id: uuid.UUID) -> None:
        """Insert the freeze-frame rows for one match's shots.

        Idempotent: a shot that already has frames is skipped wholesale, so
        re-running an ingest repairs a match rather than duplicating rows.
        """
        self.session.execute(text(_POPULATE_SQL), {"match_id": match_id})
