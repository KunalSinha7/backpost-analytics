"""One-shot Phase 1 backfill: populate team/position entities and entity FKs.

Run inside the backend container:

    python -m app.backfill_identity

Reads only columns already in the database (`soccer_match.raw`,
`event.raw_event`, `lineup.raw`), so there is no network access and no
StatsBomb round trip. Safe to re-run: every step skips rows whose FK is
already set.
"""

import json
import logging

from sqlmodel import Session

from app.core.db import engine
from app.services.identity_backfill import IdentityBackfillService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    with Session(engine) as session:
        report = IdentityBackfillService(session).run()
    print(json.dumps(report.as_dict(), indent=2))


if __name__ == "__main__":
    main()
