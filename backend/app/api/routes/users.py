import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.exceptions.user import (
    EmailAlreadyExistsError,
    IncorrectPasswordError,
    InsufficientPrivilegesError,
    PasswordUnchangedError,
    SuperuserCannotDeleteSelfError,
    UserNotFoundError,
)
from app.models import (
    Message,
    UpdatePassword,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    users, count = UserService(session).list_users(skip=skip, limit=limit)
    return UsersPublic(data=[UserPublic.model_validate(u) for u in users], count=count)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    try:
        return UserService(session).create_user(user_in)
    except EmailAlreadyExistsError:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    try:
        return UserService(session).update_user_me(current_user, user_in)
    except EmailAlreadyExistsError:
        raise HTTPException(
            status_code=409, detail="User with this email already exists"
        )


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    try:
        UserService(session).update_password_me(current_user, body)
    except IncorrectPasswordError:
        raise HTTPException(status_code=400, detail="Incorrect password")
    except PasswordUnchangedError:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    try:
        UserService(session).delete_user_me(current_user)
    except SuperuserCannotDeleteSelfError:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    try:
        return UserService(session).register_user(user_in)
    except EmailAlreadyExistsError:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    try:
        return UserService(session).get_user_by_id(user_id, current_user)
    except InsufficientPrivilegesError:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def update_user(*, session: SessionDep, user_id: uuid.UUID, user_in: UserUpdate) -> Any:
    try:
        return UserService(session).update_user(user_id, user_in)
    except UserNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    except EmailAlreadyExistsError:
        raise HTTPException(
            status_code=409, detail="User with this email already exists"
        )


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    try:
        UserService(session).delete_user(user_id, current_user)
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except SuperuserCannotDeleteSelfError:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    return Message(message="User deleted successfully")
