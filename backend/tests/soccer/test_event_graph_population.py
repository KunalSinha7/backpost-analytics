"""Population of the event-graph tables from `event.raw_event`.

Issues #31 and #32 shipped `event_relation`, `match_formation` and
`shot_freeze_frame` as one-off migration backfills, so a freshly-ingested
database left all three empty. Each entity's repository now runs that same
extraction per match from the ingest path; these tests pin the behaviour the
migration established, including idempotency, which is what makes re-running
an ingest a repair rather than a duplication.
"""

import itertools
import uuid

import pytest
from sqlmodel import Session, func, select

from app.models.event import Event
from app.models.event_relation import EventRelation
from app.models.match_formation import MatchFormation, MatchFormationSlot
from app.models.shot_freeze_frame import ShotFreezeFrame
from app.repositories.event import EventRepository
from app.repositories.event_relation import EventRelationRepository
from app.repositories.match_formation import MatchFormationRepository
from app.repositories.shot_freeze_frame import ShotFreezeFrameRepository
from tests.utils.soccer import create_competition, create_event, create_match

_ids = itertools.count(32100)


@pytest.fixture
def match_id(db: Session) -> uuid.UUID:
    """A fresh competition/match per test.

    Each test derives over a whole match, so they must not share one — and the
    statsbomb ids are unique-constrained, so the counter keeps successive
    tests from colliding on them.
    """
    n = next(_ids)
    comp = create_competition(db, statsbomb_id=n, season_id=n)
    match = create_match(db, comp.id, statsbomb_id=n * 10)
    return match.id


def _populate_all(db: Session, match_id: uuid.UUID) -> None:
    """Run every population step for a match, in the ingest path's order."""
    EventRepository(db).link_assist_events_for_match(match_id)
    EventRelationRepository(db).populate_for_match(match_id)
    MatchFormationRepository(db).populate_for_match(match_id)
    ShotFreezeFrameRepository(db).populate_for_match(match_id)


def _edges_for_match(db: Session, match_id: uuid.UUID) -> int:
    """Edges whose source event belongs to this match.

    Soccer data is wiped per module, not per test, so a global count would
    pick up rows left by earlier tests in this file.
    """
    return db.exec(  # type: ignore[return-value]
        select(func.count())
        .select_from(EventRelation)
        .join(Event, Event.id == EventRelation.event_id)  # type: ignore[arg-type]
        .where(Event.match_id == match_id)
    ).one()


def _count(db: Session, model: object, **where: object) -> int:
    stmt = select(func.count()).select_from(model)  # type: ignore[arg-type]
    for key, value in where.items():
        stmt = stmt.where(getattr(model, key) == value)  # type: ignore[attr-defined]
    return db.exec(stmt).one()  # type: ignore[return-value]


def test_derives_event_relations_from_raw_event(
    db: Session, match_id: uuid.UUID
) -> None:
    receipt_sb_id = str(uuid.uuid4())
    receipt = create_event(
        db, match_id, statsbomb_id=receipt_sb_id, type_name="Ball Receipt*", index=2
    )
    passer = create_event(
        db,
        match_id,
        statsbomb_id=str(uuid.uuid4()),
        type_name="Pass",
        index=1,
        raw_event={"related_events": [receipt_sb_id]},
    )

    _populate_all(db, match_id)
    db.commit()

    assert (
        _count(db, EventRelation, event_id=passer.id, related_event_id=receipt.id) == 1
    )
    # The source is stored literally: only the direction the feed listed.
    assert (
        _count(db, EventRelation, event_id=receipt.id, related_event_id=passer.id) == 0
    )


def test_ignores_related_events_pointing_outside_the_database(
    db: Session, match_id: uuid.UUID
) -> None:
    """A dangling reference must not create an orphan edge or fail the run."""
    create_event(
        db,
        match_id,
        statsbomb_id=str(uuid.uuid4()),
        type_name="Pass",
        index=1,
        raw_event={"related_events": [str(uuid.uuid4())]},
    )

    _populate_all(db, match_id)
    db.commit()

    assert _edges_for_match(db, match_id) == 0


def test_derives_assist_self_fks(db: Session, match_id: uuid.UUID) -> None:
    key_pass_sb_id = str(uuid.uuid4())
    shot_sb_id = str(uuid.uuid4())
    key_pass = create_event(
        db,
        match_id,
        statsbomb_id=key_pass_sb_id,
        type_name="Pass",
        index=1,
        raw_event={"pass_assisted_shot_id": shot_sb_id},
    )
    shot = create_event(
        db,
        match_id,
        statsbomb_id=shot_sb_id,
        type_name="Shot",
        index=2,
        raw_event={"shot_key_pass_id": key_pass_sb_id},
    )

    _populate_all(db, match_id)
    db.commit()
    db.refresh(shot)
    db.refresh(key_pass)

    assert shot.key_pass_event_id == key_pass.id
    assert key_pass.assisted_shot_event_id == shot.id


def test_derives_formation_and_one_slot_per_lineup_entry(
    db: Session, match_id: uuid.UUID
) -> None:
    lineup = [
        {"player": {"id": 900 + i}, "position": {"id": i}, "jersey_number": i}
        for i in range(1, 12)
    ]
    event = create_event(
        db,
        match_id,
        statsbomb_id=str(uuid.uuid4()),
        type_name="Starting XI",
        index=1,
        raw_event={"tactics": {"formation": 442, "lineup": lineup}},
    )

    _populate_all(db, match_id)
    db.commit()

    formation = db.exec(
        select(MatchFormation).where(MatchFormation.event_id == event.id)
    ).one()
    assert formation.formation == "442"
    # Unresolvable player/position ids leave the columns NULL rather than
    # dropping the slot — the "11 slots per formation" invariant holds.
    assert _count(db, MatchFormationSlot, match_formation_id=formation.id) == 11


def test_ignores_events_without_a_tactics_payload(
    db: Session, match_id: uuid.UUID
) -> None:
    create_event(
        db, match_id, statsbomb_id=str(uuid.uuid4()), type_name="Pass", index=1
    )
    _populate_all(db, match_id)
    db.commit()
    assert _count(db, MatchFormation, match_id=match_id) == 0


def test_derives_freeze_frames_with_keeper_flag(
    db: Session, match_id: uuid.UUID
) -> None:
    shot = create_event(
        db,
        match_id,
        statsbomb_id=str(uuid.uuid4()),
        type_name="Shot",
        index=1,
        raw_event={
            "shot_freeze_frame": [
                {
                    "player": {"id": 901},
                    "position": {"id": 1},
                    "location": [10.5, 20.5],
                    "teammate": False,
                },
                {
                    "player": {"id": 902},
                    "position": {"id": 17},
                    "location": [30.0, 40.0],
                    "teammate": True,
                },
            ]
        },
    )

    _populate_all(db, match_id)
    db.commit()

    frames = db.exec(
        select(ShotFreezeFrame).where(ShotFreezeFrame.event_id == shot.id)
    ).all()
    assert len(frames) == 2
    # is_keeper is derived from position.id == 1, not a source field.
    keeper = next(f for f in frames if f.is_keeper)
    assert (keeper.location_x, keeper.location_y) == (10.5, 20.5)
    assert keeper.is_teammate is False
    assert sum(1 for f in frames if f.is_teammate) == 1


def test_derivation_is_idempotent(db: Session, match_id: uuid.UUID) -> None:
    """Re-running an ingest must repair, never duplicate."""
    receipt_sb_id = str(uuid.uuid4())
    create_event(
        db, match_id, statsbomb_id=receipt_sb_id, type_name="Ball Receipt*", index=2
    )
    create_event(
        db,
        match_id,
        statsbomb_id=str(uuid.uuid4()),
        type_name="Pass",
        index=1,
        raw_event={"related_events": [receipt_sb_id]},
    )
    create_event(
        db,
        match_id,
        statsbomb_id=str(uuid.uuid4()),
        type_name="Starting XI",
        index=3,
        raw_event={
            "tactics": {
                "formation": 433,
                "lineup": [{"player": {"id": 950}, "position": {"id": 1}}],
            }
        },
    )
    create_event(
        db,
        match_id,
        statsbomb_id=str(uuid.uuid4()),
        type_name="Shot",
        index=4,
        raw_event={
            "shot_freeze_frame": [
                {"player": {"id": 951}, "position": {"id": 1}, "location": [1.0, 2.0]}
            ]
        },
    )

    _populate_all(db, match_id)
    db.commit()
    first = (
        _edges_for_match(db, match_id),
        _count(db, MatchFormation, match_id=match_id),
        _count(db, MatchFormationSlot),
        _count(db, ShotFreezeFrame),
    )

    _populate_all(db, match_id)
    db.commit()
    second = (
        _edges_for_match(db, match_id),
        _count(db, MatchFormation, match_id=match_id),
        _count(db, MatchFormationSlot),
        _count(db, ShotFreezeFrame),
    )

    assert first == second
    assert all(count > 0 for count in first)
