import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlmodel import Session, func, select

from app.models.lineup import Lineup
from app.models.lineup_position import LineupPosition
from app.models.position import Position
from app.services.identity_backfill import EmptyBackfillInputError
from app.services.resolver import normalize_external_id

logger = logging.getLogger(__name__)

FINAL_WHISTLE = "Final Whistle"


def parse_clock(value: str | None) -> int | None:
    """Parse StatsBomb's "MM:SS" match clock into seconds from kick-off.

    Verified against all 15,276 stints in the dev data: every one matches
    ``^\\d+:\\d{2}$``, and minutes run past 60 for second-half stints
    ("69:35"), so this is elapsed match time rather than a wall clock.
    """
    if value is None:
        return None
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"unrecognised match clock {value!r}")
    minutes, seconds = parts
    return int(minutes) * 60 + int(seconds)


@dataclass
class LineupPositionReport:
    stints_created: int = 0
    lineups_processed: int = 0
    resolved_to_final_whistle: int = 0
    skipped_unknown_position: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "stints_created": self.stints_created,
            "lineups_processed": self.lineups_processed,
            "resolved_to_final_whistle": self.resolved_to_final_whistle,
            "skipped_unknown_position": self.skipped_unknown_position,
            "notes": self.notes,
        }


class LineupPositionBackfillService:
    """Flattens `lineup.raw['positions']` into `lineup_position` rows.

    Reads only `lineup.raw`, captured in Phase 0, plus the event table for match
    end times — no network access. Idempotent: lineups that already have stints
    are skipped, so a partial run can be repeated.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def assert_inputs_present(self) -> None:
        with_raw = self.session.exec(
            select(func.count()).select_from(Lineup).where(Lineup.raw != None)  # noqa: E711
        ).one()
        if with_raw == 0:
            raise EmptyBackfillInputError(
                "Refusing to backfill: no lineup has a `raw` payload, which is "
                "the only place positions[] exists. Re-ingest lineups first "
                "(§7.1a — a test run deletes them)."
            )

    def _match_end_seconds(self) -> dict[uuid.UUID, int]:
        """Last observed second of each match, from its own events.

        This is what an open-ended stint resolves to. A flat 90 minutes would
        be wrong for every match — the real final whistle in this data lands
        between 90.2 and 91.0 minutes — and per-90 rates are exactly sensitive
        to that difference.
        """
        rows = self.session.execute(
            text(
                "SELECT match_id, max(minute * 60 + second) AS end_seconds "
                "FROM event GROUP BY match_id"
            )
        ).all()
        return {row[0]: int(row[1] or 0) for row in rows}

    def _positions_by_external_id(self) -> dict[str, uuid.UUID]:
        return {p.external_id: p.id for p in self.session.exec(select(Position)).all()}

    def run(self) -> LineupPositionReport:
        self.assert_inputs_present()
        report = LineupPositionReport()

        already_done = {
            row[0]
            for row in self.session.execute(
                text("SELECT DISTINCT lineup_id FROM lineup_position")
            ).all()
        }
        match_end = self._match_end_seconds()
        positions = self._positions_by_external_id()

        lineups = self.session.exec(
            select(Lineup).where(Lineup.raw != None)  # noqa: E711
        ).all()

        batch: list[LineupPosition] = []
        for lineup in lineups:
            if lineup.id in already_done:
                continue
            stints = (lineup.raw or {}).get("positions") or []
            if not stints:
                continue
            report.lineups_processed += 1

            for stint in stints:
                position_id = positions.get(
                    normalize_external_id(stint.get("position_id")) or ""
                )
                if position_id is None:
                    report.skipped_unknown_position += 1
                    continue

                from_seconds = parse_clock(stint.get("from"))
                if from_seconds is None:
                    report.skipped_unknown_position += 1
                    continue

                to_seconds = parse_clock(stint.get("to"))
                if to_seconds is None:
                    # Verified as an exact correlation across all 15,276 stints:
                    # a null `to` occurs if and only if end_reason is
                    # "Final Whistle". Falling back to from_seconds rather than
                    # a guessed 90 keeps a missing match end from inventing
                    # minutes nobody played.
                    to_seconds = match_end.get(lineup.match_id, from_seconds)
                    report.resolved_to_final_whistle += 1

                batch.append(
                    LineupPosition(
                        lineup_id=lineup.id,
                        position_id=position_id,
                        from_period=int(stint.get("from_period") or 1),
                        to_period=int(
                            stint.get("to_period") or stint.get("from_period") or 1
                        ),
                        from_seconds=from_seconds,
                        to_seconds=max(to_seconds, from_seconds),
                        start_reason=str(stint.get("start_reason") or "")[:100],
                        end_reason=str(stint.get("end_reason") or "")[:100],
                    )
                )

        if batch:
            self.session.add_all(batch)
            report.stints_created = len(batch)
        self.session.commit()
        logger.info("Lineup position backfill: %s", report.as_dict())
        return report
