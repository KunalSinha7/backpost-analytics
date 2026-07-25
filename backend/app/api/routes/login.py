from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core import security
from app.core.config import settings
from app.exceptions.user import InactiveUserError, InvalidTokenError
from app.models import Message, NewPassword, Token, UserPublic
from app.services.user import UserService
from app.utils import generate_password_reset_token, generate_reset_password_email

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    try:
        user = UserService(session).authenticate_user(
            email=form_data.username, password=form_data.password
        )
    except InvalidTokenError:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    except InactiveUserError:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    return current_user


@router.post("/password-recovery/{email}")
def recover_password(email: str, session: SessionDep) -> Message:
    UserService(session).recover_password(email)
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


@router.post("/reset-password/")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    try:
        UserService(session).reset_password(
            token=body.token, new_password=body.new_password
        )
    except InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid token")
    except InactiveUserError:
        raise HTTPException(status_code=400, detail="Inactive user")
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    user = UserService(session).get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=token
    )
    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
