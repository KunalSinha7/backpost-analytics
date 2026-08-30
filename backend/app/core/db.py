from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.models import User, UserCreate

# The unused imports below are load-bearing. Model relationships use string
# forward references to avoid circular imports, and SQLAlchemy can only resolve
# those names for classes that have been imported. Importing them here — the
# one module every entry point reaches — keeps standalone scripts working, not
# just the app, whose routes happen to import everything anyway.
from app.models.competition import (  # noqa: F401
    Competition,
    CompetitionSeason,
    Season,
)
from app.models.competition_stage import CompetitionStage  # noqa: F401
from app.models.data_source import DataSource
from app.models.event import Event  # noqa: F401
from app.models.frame360 import Frame360  # noqa: F401
from app.models.lineup import Lineup  # noqa: F401
from app.models.lineup_position import LineupPosition  # noqa: F401
from app.models.manager import Manager  # noqa: F401
from app.models.match import SoccerMatch  # noqa: F401
from app.models.player import Player  # noqa: F401
from app.models.position import Position  # noqa: F401
from app.models.referee import Referee  # noqa: F401
from app.models.stadium import Stadium  # noqa: F401
from app.models.team import Team, TeamAlias  # noqa: F401
from app.repositories.user import create_user

engine = create_engine(str(settings.DATABASE_URL or settings.SQLALCHEMY_DATABASE_URI))

STATSBOMB_SOURCE_KEY = "statsbomb"


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = create_user(session=session, user_create=user_in)

    source = session.exec(
        select(DataSource).where(DataSource.key == STATSBOMB_SOURCE_KEY)
    ).first()
    if not source:
        session.add(DataSource(key=STATSBOMB_SOURCE_KEY, name="StatsBomb"))
        session.commit()
