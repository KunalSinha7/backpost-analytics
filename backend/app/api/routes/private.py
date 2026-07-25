from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.exceptions.user import EmailAlreadyExistsError
from app.models import UserCreate, UserPublic
from app.services.user import UserService

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
    try:
        return UserService(session).create_user(user_in=user_create)
    except EmailAlreadyExistsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
