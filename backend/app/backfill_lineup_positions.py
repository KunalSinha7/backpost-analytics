"""One-shot Phase 3 backfill: flatten lineup.positions[] into lineup_position.

Run inside the backend container:

    python -m app.backfill_lineup_positions

Reads `lineup.raw` (captured in Phase 0) plus the event table for match end
times. Safe to re-run: lineups that already have stints are skipped.
"""

import json
import logging

from sqlmodel import Session

from app.core.db import engine
from app.services.lineup_position_backfill import LineupPositionBackfillService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    with Session(engine) as session:
        report = LineupPositionBackfillService(session).run()
    logger.info("Lineup position report:\n%s", json.dumps(report.as_dict(), indent=2))


if __name__ == "__main__":
    main()
