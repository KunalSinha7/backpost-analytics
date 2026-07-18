from fastapi import APIRouter

from app.api.routes import (
    competition,
    event,
    frame360,
    lineup,
    login,
    match,
    private,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)

soccer_router = APIRouter(prefix="/soccer")
soccer_router.include_router(competition.router)
soccer_router.include_router(match.router)
soccer_router.include_router(event.router)
soccer_router.include_router(lineup.router)
soccer_router.include_router(frame360.router)
api_router.include_router(soccer_router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
