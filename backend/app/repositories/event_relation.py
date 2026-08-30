"""`event_relation` — the many-to-many graph of StatsBomb `related_events`.

The edges are a projection of `event.raw_event`, so they are populated by
running the extraction rather than by inserting model instances. Issue #31
shipped this as a migration backfill only, which left the table empty on any
freshly-ingested database; `populate_for_match` is the same extraction scoped
to one match so the ingest path can keep it current.
"""

import uuid

from sqlalchemy import text
from sqlmodel import Session

# `related_events` entries are StatsBomb event UUID strings, and the events
# they reference are always within the same match, so the self-join is
# match-scoped. ON CONFLICT covers the composite primary key.
_POPULATE_SQL = """
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


class EventRelationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def populate_for_match(self, match_id: uuid.UUID) -> None:
        """Insert the relation edges for one match.

        Idempotent: an edge that already exists is left alone, so re-running an
        ingest repairs a match rather than duplicating its edges. Requires
        every event of the match to be committed first, since edges reference
        other events in the same match.
        """
        self.session.execute(text(_POPULATE_SQL), {"match_id": match_id})
