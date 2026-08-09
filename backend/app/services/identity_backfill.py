import logging
from dataclasses import dataclass, field

from typing import Any, cast

from sqlalchemy import CursorResult, Executable, text
from sqlmodel import Session, func, select

from app.models.event import Event
from app.models.match import SoccerMatch
from app.models.player import Player
from app.services.resolver import EntityResolver

logger = logging.getLogger(__name__)


class EmptyBackfillInputError(RuntimeError):
    """Raised when the tables this backfill reads are empty.

    Guards the failure mode described in §7.1a: the test suite deletes every
    row of soccer data, so "write migration -> run tests -> run backfill"
    destroys the backfill's own input. The backfill would then succeed against
    empty tables and report zero rows updated — a false green that looks
    exactly like a clean run. Refusing to start is what makes it loud.
    """


@dataclass
class BackfillReport:
    teams_created: int = 0
    aliases_created: int = 0
    positions_created: int = 0
    players_stamped: int = 0
    match_team_ids: int = 0
    event_fks: int = 0
    lineup_team_ids: int = 0
    lineup_player_ids: int = 0
    frame_event_ids: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "teams_created": self.teams_created,
            "aliases_created": self.aliases_created,
            "positions_created": self.positions_created,
            "players_stamped": self.players_stamped,
            "match_team_ids": self.match_team_ids,
            "event_fks": self.event_fks,
            "lineup_team_ids": self.lineup_team_ids,
            "lineup_player_ids": self.lineup_player_ids,
            "frame_event_ids": self.frame_event_ids,
            "notes": self.notes,
        }


class IdentityBackfillService:
    """Populates the Phase 1 entities and FKs from data already in the database.

    No network access: every source is a column the Phase 0 work captured
    (`soccer_match.raw`, `event.raw_event`, `lineup.raw`). Idempotent — each
    step only touches rows whose FK is still NULL, so a partial run can simply
    be repeated.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.resolver = EntityResolver(session)

    # ---------------------------------------------------------------- guards

    def assert_inputs_present(self) -> None:
        matches = self.session.exec(select(func.count()).select_from(SoccerMatch)).one()
        events = self.session.exec(select(func.count()).select_from(Event)).one()
        matches_with_raw = self.session.exec(
            select(func.count()).select_from(SoccerMatch).where(SoccerMatch.raw != None)  # noqa: E711
        ).one()
        if matches == 0 or events == 0:
            raise EmptyBackfillInputError(
                f"Refusing to backfill: soccer_match={matches}, event={events}. "
                "Both must be non-empty. If you just ran the test suite against "
                "this database, the soccer data was deleted (§7.1a) and must be "
                "re-ingested before the backfill can do anything meaningful."
            )
        if matches_with_raw == 0:
            raise EmptyBackfillInputError(
                "Refusing to backfill: no soccer_match row has a `raw` payload, "
                "which is where home/away team ids come from. Run "
                "MatchService.backfill_raw first."
            )

    # ----------------------------------------------------------- entity build

    def build_teams(self, report: BackfillReport) -> None:
        """Create `team` rows from the match feed first, then the event feed.

        Order is the tie-break (§6/H3): the match feed goes first and claims the
        canonical name, because its spelling is what the API emits today. The
        event feed then only fills in teams the match feed never mentioned, and
        contributes its own spelling as an alias.
        """
        before = self._count_teams()
        before_aliases = self._count_aliases()

        match_rows = self.session.execute(
            text(
                """
                SELECT DISTINCT raw->>'home_team_id' AS ext, home_team AS name,
                       home_team_gender AS gender, home_team_country_name AS country
                FROM soccer_match WHERE raw->>'home_team_id' IS NOT NULL
                UNION
                SELECT DISTINCT raw->>'away_team_id', away_team,
                       away_team_gender, away_team_country_name
                FROM soccer_match WHERE raw->>'away_team_id' IS NOT NULL
                """
            )  # type: ignore[arg-type]
        ).all()
        for ext, name, gender, country in match_rows:
            self.resolver.resolve_team(
                ext,
                name,
                authoritative_name=True,
                gender=gender,
                country_name=country,
            )

        event_rows = self.session.execute(
            text(
                """
                SELECT DISTINCT raw_event->>'team_id' AS ext, team AS name
                FROM event WHERE raw_event->>'team_id' IS NOT NULL
                UNION
                SELECT DISTINCT raw_event->>'possession_team_id', possession_team_name
                FROM event
                WHERE raw_event->>'possession_team_id' IS NOT NULL
                  AND possession_team_name IS NOT NULL
                """
            )  # type: ignore[arg-type]
        ).all()
        for ext, name in event_rows:
            self.resolver.resolve_team(ext, name, authoritative_name=False)

        self.session.commit()
        report.teams_created = self._count_teams() - before
        report.aliases_created = self._count_aliases() - before_aliases

    def build_positions(self, report: BackfillReport) -> None:
        """Build the position vocabulary from `lineup.raw`, not `raw_event`.

        §2.2 and §3 both said `event.position_id` backfills from `raw_event` at
        "100% of player events". It does not: statsbombpy flattens StatsBomb's
        nested `position: {id, name}` down to the name alone, so `raw_event` has
        no `position_id` key at all — verified 0 of 1,365,934 rows. The numeric
        ids survive only in `lineup.raw`'s `positions[]`, so the vocabulary is
        built from there and events resolve to it by name.
        """
        before = self._count_positions()
        rows = self.session.execute(
            text(
                """
                SELECT DISTINCT p->>'position_id' AS ext, p->>'position' AS name
                FROM lineup l, jsonb_array_elements((l.raw->'positions')::jsonb) p
                WHERE p->>'position_id' IS NOT NULL
                """
            )  # type: ignore[arg-type]
        ).all()
        for ext, name in rows:
            self.resolver.resolve_position(ext, name)
        self.session.commit()
        report.positions_created = self._count_positions() - before

    def stamp_players(self, report: BackfillReport) -> None:
        players = self.session.exec(
            select(Player).where(Player.source_id == None)  # noqa: E711
        ).all()
        for player in players:
            self.resolver.attach_player_source(player)
        self.session.commit()
        report.players_stamped = len(players)

    # -------------------------------------------------------------- FK fills

    def _run_update(self, statement: Executable) -> int:
        """Run a bulk UPDATE and report how many rows it touched.

        `Session.execute` is typed as returning `Result`, which has no
        `rowcount` — only the `CursorResult` a DML statement actually returns
        does. Narrowing it once here keeps the call sites free of per-call type
        ignores, and those counts are the only evidence a backfill step did
        anything.
        """
        return cast("CursorResult[Any]", self.session.execute(statement)).rowcount

    def fill_match_team_ids(self, report: BackfillReport) -> None:
        result = self._run_update(
            text(
                """
                UPDATE soccer_match m
                SET home_team_id = ht.id, away_team_id = at.id
                FROM soccer_match src
                LEFT JOIN team ht ON ht.source_id = :src
                     AND ht.external_id = (src.raw->>'home_team_id')::numeric::bigint::text
                LEFT JOIN team at ON at.source_id = :src
                     AND at.external_id = (src.raw->>'away_team_id')::numeric::bigint::text
                WHERE m.id = src.id
                  AND (m.home_team_id IS NULL OR m.away_team_id IS NULL)
                """
            ).bindparams(src=self.resolver.source_id)  # type: ignore[arg-type]
        )
        report.match_team_ids = result
        self.session.commit()

    def fill_event_fks(self, report: BackfillReport) -> None:
        """All six event FKs in one pass over the table.

        Six separate UPDATEs would mean six sequential scans of 1.4M rows and
        six rounds of dead tuples; one pass with left joins costs a single scan.

        Every id cast goes through ::numeric::bigint because the same payload
        mixes int and float representations — `team_id: 142` beside
        `player_id: 3348.0` — and a bare ::int throws on the second (§1.5/B1).
        """
        result = self._run_update(
            text(
                """
                UPDATE event e
                SET team_id = tt.id,
                    possession_team_id = pt.id,
                    player_id = pl.id,
                    pass_recipient_id = pr.id,
                    position_id = po.id,
                    substitution_replacement_id = sr.id
                FROM event src
                LEFT JOIN team tt ON tt.source_id = :src
                     AND tt.external_id = (src.raw_event->>'team_id')::numeric::bigint::text
                LEFT JOIN team pt ON pt.source_id = :src
                     AND pt.external_id = (src.raw_event->>'possession_team_id')::numeric::bigint::text
                LEFT JOIN player pl ON pl.source_id = :src
                     AND pl.external_id = (src.raw_event->>'player_id')::numeric::bigint::text
                LEFT JOIN player pr ON pr.source_id = :src
                     AND pr.external_id = (src.raw_event->>'pass_recipient_id')::numeric::bigint::text
                LEFT JOIN player sr ON sr.source_id = :src
                     AND sr.external_id = (src.raw_event->>'substitution_replacement_id')::numeric::bigint::text
                LEFT JOIN position po ON po.source_id = :src
                     AND po.name = src.raw_event->>'position'
                WHERE e.id = src.id AND e.team_id IS NULL
                """
            ).bindparams(src=self.resolver.source_id)  # type: ignore[arg-type]
        )
        report.event_fks = result
        self.session.commit()

    def fill_lineup_fks(self, report: BackfillReport) -> None:
        """Resolve lineup.team_id through the *event* feed (§1.6/B0).

        Not against the parent match's two teams. Scoping a name comparison to
        two candidates is still a name comparison, and it fails on the 20
        Marseille rows where the match feed says "Olympique de Marseille" and
        the lineup feed says "Marseille". The lineups and events feeds share a
        vocabulary; the match feed is the one carrying the alias.
        """
        team_result = self._run_update(
            text(
                """
                UPDATE lineup l
                SET team_id = t.id
                FROM (
                    SELECT DISTINCT e.match_id, e.team AS team_name,
                           (e.raw_event->>'team_id')::numeric::bigint::text AS ext
                    FROM event e
                    WHERE e.team IS NOT NULL AND e.raw_event->>'team_id' IS NOT NULL
                ) ev
                JOIN team t ON t.source_id = :src AND t.external_id = ev.ext
                WHERE l.match_id = ev.match_id
                  AND l.team_name = ev.team_name
                  AND l.team_id IS NULL
                """
            ).bindparams(src=self.resolver.source_id)  # type: ignore[arg-type]
        )
        report.lineup_team_ids = team_result

        player_result = self._run_update(
            text(
                """
                UPDATE lineup l
                SET player_id = p.id
                FROM player p
                WHERE p.statsbomb_id = l.statsbomb_player_id
                  AND l.player_id IS NULL
                """
            )  # type: ignore[arg-type]
        )
        report.lineup_player_ids = player_result
        self.session.commit()

    def fill_frame_event_ids(self, report: BackfillReport) -> None:
        """Replace frame360's soft string join with a real FK.

        `uq_frame360_event_id` means two frames pointing at one event would
        abort this statement rather than silently keeping one, so check first
        and report instead of failing the whole run.
        """
        collisions = self.session.execute(
            text(
                """
                SELECT count(*) FROM (
                    SELECT event_statsbomb_id FROM frame360
                    GROUP BY event_statsbomb_id HAVING count(*) > 1
                ) d
                """
            )  # type: ignore[arg-type]
        ).scalar_one()
        if collisions:
            report.notes.append(
                f"skipped frame360.event_id: {collisions} event_statsbomb_id "
                "values map to more than one frame, which the UNIQUE constraint "
                "forbids"
            )
            return

        result = self._run_update(
            text(
                """
                UPDATE frame360 f
                SET event_id = e.id
                FROM event e
                WHERE e.statsbomb_id = f.event_statsbomb_id
                  AND f.event_id IS NULL
                """
            )  # type: ignore[arg-type]
        )
        report.frame_event_ids = result
        self.session.commit()

    # ------------------------------------------------------------------- run

    def run(self) -> BackfillReport:
        self.assert_inputs_present()
        report = BackfillReport()
        self.build_teams(report)
        self.build_positions(report)
        self.stamp_players(report)
        self.fill_match_team_ids(report)
        self.fill_event_fks(report)
        self.fill_lineup_fks(report)
        self.fill_frame_event_ids(report)
        logger.info("Identity backfill: %s", report.as_dict())
        return report

    # --------------------------------------------------------------- helpers

    def _count_teams(self) -> int:
        return self.session.execute(text("SELECT count(*) FROM team")).scalar_one()  # type: ignore[arg-type]

    def _count_aliases(self) -> int:
        return self.session.execute(text("SELECT count(*) FROM team_alias")).scalar_one()  # type: ignore[arg-type]

    def _count_positions(self) -> int:
        return self.session.execute(text("SELECT count(*) FROM position")).scalar_one()  # type: ignore[arg-type]


__all__ = [
    "BackfillReport",
    "EmptyBackfillInputError",
    "IdentityBackfillService",
]
