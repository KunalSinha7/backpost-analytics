"""One-shot Phase 2 backfill: populate `competition` and `season` from editions.

Run inside the backend container:

    python -m app.backfill_competition_split

Purely in-database — every value already lives on `competition_season`.
Safe to re-run: only editions with a NULL link are touched.
"""

import json
import logging

from sqlmodel import Session

from app.core.db import engine
from app.services.competition_split_backfill import CompetitionSplitBackfillService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    with Session(engine) as session:
        report = CompetitionSplitBackfillService(session).run()
    logger.info(
        "Competition split report:\n%s", json.dumps(report.as_dict(), indent=2)
    )


if __name__ == "__main__":
    main()
