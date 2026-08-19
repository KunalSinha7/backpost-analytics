from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.models import User, UserCreate

# Every table model is imported here, not just the ones this module uses, and
# the unused ones are load-bearing.
#
# `CompetitionSeason.matches` targets "SoccerMatch" as a string forward
# reference — it has to, since `app.models.match` imports `CompetitionSeason`
# and a direct import would be circular. SQLAlchemy resolves that name when it
# configures mappers, which fails outright if the class was never imported:
#
#   InvalidRequestError: When initializing mapper Mapper[CompetitionSeason],
#   expression 'SoccerMatch' failed to locate a name ('SoccerMatch')
#
# The FastAPI app never hits this because its routes import everything
# transitively. Standalone scripts do: `python -m app.backfill_lineup_positions`
# crashed on a freshly built database for precisely this reason, and only
# there. Importing them at the one choke point every entry point already goes
# through — this module, for `engine` — fixes all of them at once.
from app.models.competition import (  # noqa: F401
    Competition,
    CompetitionSeason,
    Season,
)
from app.models.data_source import DataSource
from app.models.event import Event  # noqa: F401
from app.models.frame360 import Frame360  # noqa: F401
from app.models.lineup import Lineup  # noqa: F401
from app.models.lineup_position import LineupPosition  # noqa: F401
from app.models.match import SoccerMatch  # noqa: F401
from app.models.player import Player  # noqa: F401
from app.models.position import Position  # noqa: F401
from app.models.team import Team, TeamAlias  # noqa: F401
from app.repositories.user import create_user

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

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
