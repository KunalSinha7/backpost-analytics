import uuid

from sqlmodel import Session, col, func, select

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.exceptions.user import (
    EmailAlreadyExistsError,
    IncorrectPasswordError,
    InsufficientPrivilegesError,
    PasswordUnchangedError,
    SuperuserCannotDeleteSelfError,
    UserNotFoundError,
)
from app.models import UpdatePassword, User, UserCreate, UserRegister, UserUpdate, UserUpdateMe
from app.repositories.user import create_user, get_user_by_email, update_user
from app.utils import generate_new_account_email, send_email


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_users(self, skip: int = 0, limit: int = 100) -> tuple[list[User], int]:
        count = self.session.exec(select(func.count()).select_from(User)).one()
        users = self.session.exec(
            select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
        ).all()
        return list(users), count

    def create_user(self, user_in: UserCreate) -> User:
        if get_user_by_email(session=self.session, email=user_in.email):
            raise EmailAlreadyExistsError(user_in.email)
        user = create_user(session=self.session, user_create=user_in)
        if settings.emails_enabled and user_in.email:
            email_data = generate_new_account_email(
                email_to=user_in.email,
                username=user_in.email,
                password=user_in.password,
            )
            send_email(
                email_to=user_in.email,
                subject=email_data.subject,
                html_content=email_data.html_content,
            )
        return user

    def register_user(self, user_in: UserRegister) -> User:
        if get_user_by_email(session=self.session, email=user_in.email):
            raise EmailAlreadyExistsError(user_in.email)
        return create_user(session=self.session, user_create=UserCreate.model_validate(user_in))

    def get_user_by_id(self, user_id: uuid.UUID, current_user: User) -> User:
        user = self.session.get(User, user_id)
        if user == current_user:
            return user
        if not current_user.is_superuser:
            raise InsufficientPrivilegesError()
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    def update_user_me(self, current_user: User, user_in: UserUpdateMe) -> User:
        if user_in.email:
            existing = get_user_by_email(session=self.session, email=user_in.email)
            if existing and existing.id != current_user.id:
                raise EmailAlreadyExistsError(user_in.email)
        current_user.sqlmodel_update(user_in.model_dump(exclude_unset=True))
        self.session.add(current_user)
        self.session.commit()
        self.session.refresh(current_user)
        return current_user

    def update_password_me(self, current_user: User, body: UpdatePassword) -> None:
        verified, _ = verify_password(body.current_password, current_user.hashed_password)
        if not verified:
            raise IncorrectPasswordError()
        if body.current_password == body.new_password:
            raise PasswordUnchangedError()
        current_user.hashed_password = get_password_hash(body.new_password)
        self.session.add(current_user)
        self.session.commit()

    def delete_user_me(self, current_user: User) -> None:
        if current_user.is_superuser:
            raise SuperuserCannotDeleteSelfError()
        self.session.delete(current_user)
        self.session.commit()

    def update_user(self, user_id: uuid.UUID, user_in: UserUpdate) -> User:
        db_user = self.session.get(User, user_id)
        if not db_user:
            raise UserNotFoundError(user_id)
        if user_in.email:
            existing = get_user_by_email(session=self.session, email=user_in.email)
            if existing and existing.id != user_id:
                raise EmailAlreadyExistsError(user_in.email)
        return update_user(session=self.session, db_user=db_user, user_in=user_in)

    def delete_user(self, user_id: uuid.UUID, current_user: User) -> None:
        user = self.session.get(User, user_id)
        if not user:
            raise UserNotFoundError(user_id)
        if user == current_user:
            raise SuperuserCannotDeleteSelfError()
        self.session.delete(user)
        self.session.commit()
