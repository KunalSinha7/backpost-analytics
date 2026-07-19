from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.models import UserCreate, UserPublic
from app.repositories.user import create_user as create_user_in_db

router = APIRouter(tags=["private"], prefix="/private")


class PrivateUserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    is_verified: bool = False


@router.post("/users/", response_model=UserPublic)
def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    user_create = UserCreate(
        email=user_in.email,
        full_name=user_in.full_name,
        password=user_in.password,
    )
    return create_user_in_db(session=session, user_create=user_create)
