"""Golden-response + OpenAPI snapshot harness (Phase 0, §7.1).

Every later phase of ``database-normalization.md`` gates on "responses
identical except the enumerated drift set" and "diff ``openapi.json`` per
phase". This module is that gate. The snapshots under
``backend/tests/snapshots/`` are committed files; a phase that changes an API
response or the schema must show the delta as a reviewed diff.

Regenerating
------------
Snapshots are never rewritten by a normal run. To re-record after an
*intentional* change, from the repo root::

    docker compose exec -T -e UPDATE_SNAPSHOTS=1 backend \\
        python -m pytest tests/test_api_snapshots.py
    docker compose cp backend:/app/backend/tests/snapshots/. \\
        backend/tests/snapshots/

The second command is required: compose syncs ./backend into the container but
not back out, so without it the new files exist only inside the container.
(Note ``scripts/tests-start.sh`` forwards its argument to the coverage report
title, not to pytest — it always runs the whole suite. Use ``pytest`` directly
to target this file.)

Each snapshot test then reports as *skipped* — nothing was asserted — and the
new content shows up as a git diff to review. Without the env var a missing or
drifted snapshot is a hard failure, so a forgotten snapshot cannot pass in CI.

Reproducibility
---------------
Snapshots are taken against fixtures seeded by this module, never against the
dev database — the latter holds ~376k events and cannot be reproduced in CI.
The ``seeded`` fixture clears all soccer tables first, so the snapshots do not
depend on which test modules ran before this one. Random primary keys are
masked to ``<uuid:N>`` tokens by ``tests.utils.snapshots``; the fixtures give
every row a distinct value on its endpoint's ``ORDER BY`` key so the mask
numbering is stable.

The OpenAPI snapshot is database-independent but *is* environment-dependent:
it was recorded with ``ENVIRONMENT=local``, which mounts the ``/private``
router. Running under another environment will drop those paths and fail the
diff.
"""

import json
from collections.abc import Generator
from typing import Any, NamedTuple, TypeVar

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, delete

from app.core.config import settings
from app.models.competition import Competition
from app.models.match import SoccerMatch
from app.models.player import Player

# conftest owns the wipe order across the soccer tables; reuse it rather than
# maintaining a second copy that can drift as tables are added.
from tests.conftest import _wipe_soccer_data
from tests.utils.snapshots import (
    assert_matches_snapshot,
    canonicalize,
    normalize_openapi,
)
from tests.utils.soccer import (
    create_competition,
    create_event,
    create_frame,
    create_lineup,
    create_match,
)

SOCCER = f"{settings.API_V1_STR}/soccer"

T = TypeVar("T", bound=SQLModel)


class Seed(NamedTuple):
    competition_with_matches: Competition
    competition_without_matches: Competition
    match_with_events: SoccerMatch
    match_without_events: SoccerMatch


def _update(session: Session, obj: T, **fields: Any) -> T:
    """Populate columns the shared fixture helpers do not expose."""
    for name, value in fields.items():
        setattr(obj, name, value)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def _reset(session: Session) -> None:
    _wipe_soccer_data(session)
    # _wipe_soccer_data does not cover `player`; it has no inbound FKs
    # (lineup joins it by statsbomb_id), so an unordered delete is safe.
    session.execute(delete(Player))
    session.commit()


def _seed(session: Session) -> Seed:
    """Seed a small, fully deterministic dataset.

    Rows are paired: one with every optional column populated, one left at its
    defaults, so both the "value" and the "null" rendering of each field is in
    the snapshot.
    """
    comp_a = _update(
        session,
        create_competition(
            session,
            statsbomb_id=90001,
            season_id=90001,
            competition_name="Snapshot Alpha League",
            country_name="Snapshotland",
            competition_gender="male",
            season_name="2098/2099",
        ),
        match_updated="2099-01-02T03:04:05.000000",
        match_available="2099-01-02T03:04:05.000000",
        match_updated_360="2099-01-02T03:04:05.000000",
        match_available_360="2099-01-02T03:04:05.000000",
    )
    comp_b = create_competition(
        session,
        statsbomb_id=90002,
        season_id=90002,
        competition_name="Snapshot Beta Cup",
        country_name="Snapshotland",
        competition_gender="female",
        competition_international=True,
        season_name="2099",
    )

    match_1 = _update(
        session,
        create_match(
            session,
            comp_a.id,
            statsbomb_id=91001,
            match_date="2099-03-01",
            home_team="Snapshot Rovers",
            away_team="Snapshot United",
            home_score=2,
            away_score=1,
            match_status_360="available",
        ),
        kick_off="20:00:00.000",
        stadium="Snapshot Arena",
        referee="Ada Referee",
        match_week=7,
        competition_stage_name="Regular Season",
        home_team_gender="male",
        away_team_gender="male",
        home_team_country_name="Snapshotland",
        away_team_country_name="Snapshotland",
        home_team_group="Group A",
        away_team_group="Group B",
        home_manager_name="Home Manager",
        away_manager_name="Away Manager",
        match_status="available",
        last_updated="2099-01-02T03:04:05.000000",
    )
    match_2 = create_match(
        session,
        comp_a.id,
        statsbomb_id=91002,
        match_date="2099-02-01",
        home_team="Snapshot City",
        away_team="Snapshot Rovers",
        home_score=None,
        away_score=None,
    )

    _update(
        session,
        create_event(
            session,
            match_1.id,
            statsbomb_id="00000000-0000-4000-8000-000000000001",
            index=1,
            period=1,
            minute=0,
            second=0,
            type_name="Kick Off",
            team="Snapshot Rovers",
        ),
        timestamp="00:00:00.000",
    )
    _update(
        session,
        create_event(
            session,
            match_1.id,
            statsbomb_id="00000000-0000-4000-8000-000000000002",
            index=2,
            period=1,
            minute=3,
            second=14,
            type_name="Pass",
            team="Snapshot Rovers",
            player="Snapshot Alpha",
            possession=2,
            end_location_x=72.5,
            end_location_y=41.0,
        ),
        timestamp="00:03:14.159",
        possession_team_name="Snapshot Rovers",
        play_pattern_name="Regular Play",
        location_x=60.0,
        location_y=40.0,
        pass_recipient="Snapshot Bravo",
        duration=1.25,
        under_pressure=True,
    )
    _update(
        session,
        create_event(
            session,
            match_1.id,
            statsbomb_id="00000000-0000-4000-8000-000000000003",
            index=3,
            period=2,
            minute=61,
            second=2,
            type_name="Shot",
            team="Snapshot United",
            player="Snapshot Charlie",
            possession=3,
            end_location_x=120.0,
            end_location_y=40.0,
        ),
        timestamp="00:16:02.000",
        possession_team_name="Snapshot United",
        play_pattern_name="From Counter",
        location_x=104.0,
        location_y=38.0,
        duration=0.5,
        off_camera=False,
        out=False,
    )

    _update(
        session,
        create_lineup(
            session,
            match_1.id,
            team_name="Snapshot Rovers",
            statsbomb_player_id=95001,
            player_name="Snapshot Alpha",
            jersey_number=1,
        ),
        player_nickname="Alpha",
        country_name="Snapshotland",
    )
    create_lineup(
        session,
        match_1.id,
        team_name="Snapshot Rovers",
        statsbomb_player_id=95002,
        player_name="Snapshot Bravo",
        jersey_number=10,
    )
    create_lineup(
        session,
        match_1.id,
        team_name="Snapshot United",
        statsbomb_player_id=96001,
        player_name="Unregistered Player",
        jersey_number=7,
        started=False,
    )
    # Second appearance for Alpha only — makes PlayerPublic.match_count vary
    # across the seeded players instead of being uniformly 1.
    create_lineup(
        session,
        match_2.id,
        team_name="Snapshot Rovers",
        statsbomb_player_id=95001,
        player_name="Snapshot Alpha",
        jersey_number=1,
    )

    session.add_all(
        [
            Player(
                statsbomb_id=95001,
                name="Snapshot Alpha",
                nickname="Alpha",
                nationality="Snapshotland",
            ),
            Player(statsbomb_id=95002, name="Snapshot Bravo"),
            # No lineup rows: exercises the outer join's match_count == 0 path.
            Player(statsbomb_id=95003, name="Snapshot Charlie"),
        ]
    )
    session.commit()

    create_frame(session, match_1.id, "00000000-0000-4000-8000-000000000003")

    return Seed(comp_a, comp_b, match_1, match_2)


@pytest.fixture(scope="module")
def seeded(db: Session) -> Generator[Seed, None, None]:
    _reset(db)
    seed = _seed(db)
    yield seed
    _reset(db)


def _get(client: TestClient, path: str, **params: Any) -> Any:
    response = client.get(f"{SOCCER}{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# ── Schema ────────────────────────────────────────────────────────────────
# Database-independent, and the only check that sees field renames and
# changes to a model's `required` list (§6) — neither shows up in a
# response-body diff.


def test_openapi_schema_snapshot(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/openapi.json")
    assert response.status_code == 200, response.text
    assert_matches_snapshot("openapi.json", normalize_openapi(response.json()))


# ── Golden responses ──────────────────────────────────────────────────────


@pytest.mark.usefixtures("seeded")
def test_competitions_snapshot(client: TestClient) -> None:
    assert_matches_snapshot("competitions.json", _get(client, "/competitions/"))


@pytest.mark.usefixtures("seeded")
def test_competitions_has_events_snapshot(client: TestClient) -> None:
    assert_matches_snapshot(
        "competitions_has_events.json",
        _get(client, "/competitions/", has_events=True),
    )


@pytest.mark.usefixtures("seeded")
def test_matches_snapshot(client: TestClient) -> None:
    assert_matches_snapshot("matches.json", _get(client, "/matches/"))


def test_matches_by_competition_snapshot(client: TestClient, seeded: Seed) -> None:
    assert_matches_snapshot(
        "matches_by_competition.json",
        _get(
            client,
            "/matches/",
            competition_id=str(seeded.competition_with_matches.id),
        ),
    )


@pytest.mark.usefixtures("seeded")
def test_match_teams_snapshot(client: TestClient) -> None:
    assert_matches_snapshot("match_teams.json", _get(client, "/matches/teams"))


def test_events_snapshot(client: TestClient, seeded: Seed) -> None:
    assert_matches_snapshot(
        "events.json",
        _get(client, "/events/", match_id=str(seeded.match_with_events.id)),
    )


def test_events_filtered_snapshot(client: TestClient, seeded: Seed) -> None:
    assert_matches_snapshot(
        "events_filtered.json",
        _get(
            client,
            "/events/",
            match_id=str(seeded.match_with_events.id),
            type_name="Pass",
        ),
    )


def test_lineups_snapshot(client: TestClient, seeded: Seed) -> None:
    assert_matches_snapshot(
        "lineups.json",
        _get(client, "/lineups/", match_id=str(seeded.match_with_events.id)),
    )


@pytest.mark.usefixtures("seeded")
def test_players_snapshot(client: TestClient) -> None:
    assert_matches_snapshot("players.json", _get(client, "/players/"))


@pytest.mark.usefixtures("seeded")
def test_players_name_search_snapshot(client: TestClient) -> None:
    assert_matches_snapshot(
        "players_name_search.json",
        _get(client, "/players/", name_search="Bravo"),
    )


def test_frames_snapshot(client: TestClient, seeded: Seed) -> None:
    assert_matches_snapshot(
        "frames.json",
        _get(client, "/frames/", match_id=str(seeded.match_with_events.id)),
    )


# ── Harness self-check ────────────────────────────────────────────────────


def test_snapshot_is_stable_across_repeated_reads(
    client: TestClient, seeded: Seed
) -> None:
    """A snapshot that is not reproducible is worse than no snapshot.

    Guards the two ways this harness can rot into a flaky test: an endpoint
    losing its deterministic ORDER BY, and the UUID mask depending on
    something other than response order.
    """
    match_id = str(seeded.match_with_events.id)
    for path, params in (
        ("/competitions/", {}),
        ("/matches/", {}),
        ("/lineups/", {"match_id": match_id}),
        ("/players/", {}),
    ):
        first = canonicalize(_get(client, path, **params))
        second = canonicalize(_get(client, path, **params))
        assert first == second, f"{path} is not reproducible across reads"


def test_uuid_mask_is_referentially_consistent(
    client: TestClient, seeded: Seed
) -> None:
    """The mask must preserve id equality, or cross-entity drift goes unseen."""
    match_id = str(seeded.match_with_events.id)
    events = _get(client, "/events/", match_id=match_id)
    masked_text = canonicalize(events)
    assert match_id not in masked_text

    masked = json.loads(masked_text)
    tokens = {event["match_id"] for event in masked["data"]}
    assert len(masked["data"]) == 3
    assert len(tokens) == 1, "events of one match must share one match_id token"
    assert tokens.pop().startswith("<uuid:")
