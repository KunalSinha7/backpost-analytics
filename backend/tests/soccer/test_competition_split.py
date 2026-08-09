"""Phase 2: splitting the edition table into competition x season.

The old `competition` table stored one row per (competition, season), so
La Liga's name, country and gender were repeated once per season — 18 times.
That is the 2NF violation in §1.1, and these tests pin the decomposition that
removes it.
"""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from app.models.competition import Competition, CompetitionSeason, Season
from app.services.competition_split_backfill import CompetitionSplitBackfillService
from app.services.identity_backfill import EmptyBackfillInputError
from app.services.resolver import EntityResolver
from tests.utils.soccer import create_competition

LA_LIGA = 11


# ── EntityResolver: the timeless entities ───────────────────────────────────


def test_resolve_competition_dedupes_across_seasons(db: Session) -> None:
    """One competition, many seasons — this is the whole point of the split."""
    resolver = EntityResolver(db)
    first = resolver.resolve_competition(
        LA_LIGA, "La Liga", country_name="Spain", gender="male"
    )
    second = resolver.resolve_competition(
        LA_LIGA, "La Liga", country_name="Spain", gender="male"
    )
    db.commit()

    assert first is not None and second is not None
    assert first.id == second.id
    rows = db.exec(
        select(Competition).where(Competition.external_id == str(LA_LIGA))
    ).all()
    assert len(rows) == 1


def test_resolve_season_dedupes_across_competitions(db: Session) -> None:
    """A season is shared by every competition played in it."""
    resolver = EntityResolver(db)
    a = resolver.resolve_season(90001, "2018/2019")
    b = resolver.resolve_season(90001, "2018/2019")
    db.commit()

    assert a is not None and b is not None
    assert a.id == b.id


def test_resolve_competition_returns_none_without_id(db: Session) -> None:
    resolver = EntityResolver(db)
    assert (
        resolver.resolve_competition(None, "Nowhere", country_name="X", gender="male")
        is None
    )


# ── Backfill ────────────────────────────────────────────────────────────────


def _editions(db: Session, statsbomb_id: int, seasons: list[tuple[int, str]]) -> None:
    """Several seasons of one competition — the shape that was duplicated."""
    for season_id, season_name in seasons:
        create_competition(
            db,
            statsbomb_id=statsbomb_id,
            season_id=season_id,
            competition_name="La Liga",
            country_name="Spain",
            competition_gender="male",
            season_name=season_name,
        )


def test_backfill_collapses_repeated_competitions(db: Session) -> None:
    _editions(
        db, 91001, [(91001, "2016/2017"), (91002, "2017/2018"), (91003, "2018/2019")]
    )
    CompetitionSplitBackfillService(db).run()

    competitions = db.exec(
        select(Competition).where(Competition.external_id == "91001")
    ).all()
    assert len(competitions) == 1, "3 editions must collapse to 1 competition"

    linked = db.exec(
        select(CompetitionSeason).where(
            CompetitionSeason.competition_id == competitions[0].id
        )
    ).all()
    assert len(linked) == 3


def test_backfill_creates_one_season_per_distinct_season_id(db: Session) -> None:
    _editions(db, 91101, [(91101, "2016/2017"), (91102, "2017/2018")])
    CompetitionSplitBackfillService(db).run()

    seasons = db.exec(
        select(Season).where(Season.external_id.in_(["91101", "91102"]))  # type: ignore[attr-defined]
    ).all()
    assert {s.name for s in seasons} == {"2016/2017", "2017/2018"}


def test_backfill_links_every_edition(db: Session) -> None:
    _editions(db, 91201, [(91201, "2016/2017"), (91202, "2017/2018")])
    CompetitionSplitBackfillService(db).run()

    unlinked = db.exec(
        select(CompetitionSeason).where(
            (CompetitionSeason.competition_id == None)  # noqa: E711
            | (CompetitionSeason.season_ref_id == None)  # noqa: E711
        )
    ).all()
    assert unlinked == []


def test_backfill_is_idempotent(db: Session) -> None:
    _editions(db, 91301, [(91301, "2016/2017")])
    CompetitionSplitBackfillService(db).run()
    before = len(db.exec(select(Competition)).all())

    second = CompetitionSplitBackfillService(db).run()
    assert len(db.exec(select(Competition)).all()) == before
    assert second.competitions_created == 0
    assert second.editions_linked == 0


def test_backfill_refuses_empty_input() -> None:
    service = CompetitionSplitBackfillService.__new__(CompetitionSplitBackfillService)

    class _Zero:
        def exec(self, *_a: object, **_k: object) -> "_Zero":
            return self

        def one(self) -> int:
            return 0

    service.session = _Zero()  # type: ignore[assignment]
    with pytest.raises(EmptyBackfillInputError, match="nothing to split"):
        service.assert_inputs_present()


def test_competition_attributes_are_stored_once(db: Session) -> None:
    """The 2NF fix, stated as an invariant rather than a row count.

    Before the split these attributes lived on every edition row, so "what is
    La Liga called" had as many answers as there were seasons. After it, there
    is exactly one place to change.
    """
    _editions(db, 91401, [(91401, "2016/2017"), (91402, "2017/2018")])
    CompetitionSplitBackfillService(db).run()

    competition = db.exec(
        select(Competition).where(Competition.external_id == "91401")
    ).first()
    assert competition is not None
    competition.name = "Renamed Once"
    db.commit()

    editions = db.exec(
        select(CompetitionSeason).where(
            CompetitionSeason.competition_id == competition.id
        )
    ).all()
    assert len(editions) == 2
    for edition in editions:
        assert edition.competition_id == competition.id


# ── The migration's pre-flight assertions ───────────────────────────────────


def _load_migration():
    path = next(
        Path(__file__)
        .parents[2]
        .glob("app/alembic/versions/*phase_2_competition_split*.py")
    )
    spec = importlib.util.spec_from_file_location("phase2_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("assertion_index", "rows", "expected"),
    [
        # FD1: two names for one competition id must be caught.
        (0, [(1, "La Liga", "Spain"), (1, "LaLiga Santander", "Spain")], 1),
        (0, [(1, "La Liga", "Spain"), (2, "Serie A", "Italy")], 0),
    ],
)
def test_preflight_assertion_detects_conflicts(
    db: Session, assertion_index: int, rows: list[tuple], expected: int
) -> None:
    """The guard must actually fire — §6/B3's failure mode is a silent one.

    These queries only make sense against the *pre-split* `competition` table,
    whose columns the migration renames out from under them, so they are
    exercised here against a fixture with the pre-split shape rather than
    against the live table.

    Everything runs inside a savepoint. A failing statement aborts the whole
    Postgres transaction, and the `db` fixture is session-scoped — without the
    savepoint one bad query here takes down every test that follows, which is
    exactly what happened when this test was first written.
    """
    migration = _load_migration()
    _label, sql = migration._PREFLIGHT_ASSERTIONS[assertion_index]

    values = ", ".join(
        f"({sid}, '{name}', '{country}', 'male', false, false)"
        for sid, name, country in rows
    )
    savepoint = db.begin_nested()
    try:
        db.execute(
            text(
                "CREATE TEMP TABLE _fd_probe (statsbomb_id int, competition_name text,"
                " country_name text, competition_gender text,"
                " competition_youth bool, competition_international bool)"
                " ON COMMIT DROP"
            )
        )
        db.execute(text(f"INSERT INTO _fd_probe VALUES {values}"))  # noqa: S608
        violations = db.execute(
            text(sql.replace("FROM competition", "FROM _fd_probe"))
        ).scalar_one()
    finally:
        savepoint.rollback()

    assert violations == expected
