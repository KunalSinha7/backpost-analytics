import uuid
from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, delete, select

from app.core.config import settings
from app.core.db import engine, init_db
from app.core.security import get_password_hash, verify_password
from app.main import app
from app.models import User
from app.models.competition import Competition, CompetitionSeason, Season
from app.models.event import Event
from app.models.frame360 import Frame360
from app.models.lineup import Lineup
from app.models.lineup_position import LineupPosition
from app.models.match import SoccerMatch
from app.models.player import Player
from app.models.position import Position
from app.models.team import Team, TeamAlias
from app.repositories.user import create_user as _original_create_user
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers

_test_user_ids: set[uuid.UUID] = set()


def _assert_disposable_database() -> None:
    """Refuse to run against a database that isn't ours to destroy.

    The fixtures below delete every row of soccer data unconditionally, and the
    engine is built from ``settings.POSTGRES_DB`` at import time — so pointing
    the suite at the development database is one env var away, and has wiped it
    before. Requiring a ``_test`` suffix makes that mistake loud instead of
    destructive. ``scripts/tests-start.sh`` sets it; running pytest by hand
    without it fails here rather than midway through the first fixture.
    """
    db_name = settings.POSTGRES_DB
    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run: the test suite deletes all soccer data, but "
            f"POSTGRES_DB is {db_name!r}, which is not a test database.\n"
            f"Run via `bash scripts/tests-start.sh`, or set "
            f"POSTGRES_DB={db_name}_test explicitly."
        )


def _wipe_soccer_data(session: Session) -> None:
    """Delete all soccer test data respecting FK order: children before parents."""
    _assert_disposable_database()
    session.execute(delete(Event))
    session.execute(delete(Frame360))
    session.execute(delete(LineupPosition))
    session.execute(delete(Lineup))
    session.execute(delete(SoccerMatch))
    session.execute(delete(CompetitionSeason))
    # These carry UNIQUE(source_id, external_id), so a row leaked by a previous
    # run makes the next resolver test fail on a constraint rather than on its
    # own assertion.
    session.execute(delete(TeamAlias))
    session.execute(delete(Team))
    session.execute(delete(Position))
    session.execute(delete(Player))
    session.execute(delete(Competition))
    session.execute(delete(Season))
    session.commit()


def _tracking_create_user(**kwargs: object) -> User:
    user = _original_create_user(**kwargs)  # type: ignore[arg-type]
    _test_user_ids.add(user.id)
    return user


def _reset_users(session: Session) -> None:
    """Return the user table to a known state before the run starts.

    Teardown only runs when the suite exits normally, so a crashed run leaks
    every user it created and the next run fails on whichever test re-creates
    one. `init_db` cannot repair this, since it only acts when the superuser is
    absent. Cleaning up front makes the suite self-healing regardless of how
    the previous run ended.
    """
    _assert_disposable_database()
    session.execute(delete(User).where(col(User.is_superuser).is_(False)))
    session.commit()

    superuser = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    # verify_password returns (is_valid, upgraded_hash), so the [0] matters:
    # truth-testing the tuple itself is always True.
    password_ok = superuser is not None and bool(
        verify_password(settings.FIRST_SUPERUSER_PASSWORD, superuser.hashed_password)[0]
    )
    if superuser is not None and not password_ok:
        superuser.hashed_password = get_password_hash(settings.FIRST_SUPERUSER_PASSWORD)
        session.add(superuser)
        session.commit()


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        init_db(session)  # creates superuser before tracking starts
        _reset_users(session)
        _wipe_soccer_data(session)
        with (
            patch("app.repositories.user.create_user", _tracking_create_user),
            patch("app.services.user.create_user", _tracking_create_user),
        ):
            yield session
        _wipe_soccer_data(session)
        if _test_user_ids:
            session.execute(delete(User).where(User.id.in_(_test_user_ids)))
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
