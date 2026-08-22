"""EventRelation and the event self-FKs (issue #31).

These exercise the model/schema directly (there is no repository or service
layer for the event graph yet — the issue's scope is the normalized storage,
not a new API surface) against the real Postgres test database, so the
composite primary key, both FK columns, and the two self-FKs on `event` are
all verified against the schema the migration actually creates.
"""

import uuid

import pytest
from sqlmodel import Session, select

from app.models.event import Event
from app.models.event_relation import EventRelation
from tests.utils.soccer import create_competition, create_event, create_match


@pytest.fixture(scope="module")
def match_id(db: Session) -> uuid.UUID:
    comp = create_competition(db, statsbomb_id=31000, season_id=31000)
    match = create_match(db, comp.id, statsbomb_id=310000)
    return match.id


def test_event_relation_round_trips_both_directions(
    db: Session, match_id: uuid.UUID
) -> None:
    pass_event = create_event(
        db, match_id, statsbomb_id=str(uuid.uuid4()), type_name="Pass", index=1
    )
    receipt_event = create_event(
        db,
        match_id,
        statsbomb_id=str(uuid.uuid4()),
        type_name="Ball Receipt*",
        index=2,
    )

    db.add(EventRelation(event_id=pass_event.id, related_event_id=receipt_event.id))
    db.add(EventRelation(event_id=receipt_event.id, related_event_id=pass_event.id))
    db.commit()

    forward = db.exec(
        select(EventRelation).where(EventRelation.event_id == pass_event.id)
    ).all()
    backward = db.exec(
        select(EventRelation).where(EventRelation.event_id == receipt_event.id)
    ).all()

    assert [r.related_event_id for r in forward] == [receipt_event.id]
    assert [r.related_event_id for r in backward] == [pass_event.id]


def test_event_relation_cascades_on_event_delete(
    db: Session, match_id: uuid.UUID
) -> None:
    event_a = create_event(
        db, match_id, statsbomb_id=str(uuid.uuid4()), type_name="Duel", index=3
    )
    event_b = create_event(
        db, match_id, statsbomb_id=str(uuid.uuid4()), type_name="Duel", index=4
    )
    db.add(EventRelation(event_id=event_a.id, related_event_id=event_b.id))
    db.add(EventRelation(event_id=event_b.id, related_event_id=event_a.id))
    db.commit()

    db.delete(db.get(Event, event_a.id))
    db.commit()

    remaining = db.exec(
        select(EventRelation).where(
            (EventRelation.event_id == event_a.id)
            | (EventRelation.related_event_id == event_a.id)
        )
    ).all()
    assert remaining == []
    # The other side of the pair is untouched.
    assert db.get(Event, event_b.id) is not None


def test_key_pass_and_assisted_shot_self_fks(
    db: Session, match_id: uuid.UUID
) -> None:
    key_pass = create_event(
        db, match_id, statsbomb_id=str(uuid.uuid4()), type_name="Pass", index=5
    )
    shot = create_event(
        db, match_id, statsbomb_id=str(uuid.uuid4()), type_name="Shot", index=6
    )

    shot.key_pass_event_id = key_pass.id
    key_pass.assisted_shot_event_id = shot.id
    db.add(shot)
    db.add(key_pass)
    db.commit()
    db.refresh(shot)
    db.refresh(key_pass)

    assert shot.key_pass_event_id == key_pass.id
    assert key_pass.assisted_shot_event_id == shot.id

    # Deleting the key pass clears the shot's attribution rather than
    # blocking the delete (ondelete="SET NULL").
    db.delete(db.get(Event, key_pass.id))
    db.commit()
    db.refresh(shot)
    assert shot.key_pass_event_id is None
