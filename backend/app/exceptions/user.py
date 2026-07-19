import uuid


class UserNotFoundError(Exception):
    def __init__(self, user_id: uuid.UUID) -> None:
        super().__init__(f"User not found: id={user_id}")
        self.user_id = user_id


class EmailAlreadyExistsError(Exception):
    def __init__(self, email: str) -> None:
        super().__init__(f"User with email already exists: {email}")
        self.email = email


class IncorrectPasswordError(Exception):
    pass


class PasswordUnchangedError(Exception):
    pass


class SuperuserCannotDeleteSelfError(Exception):
    pass


class InsufficientPrivilegesError(Exception):
    pass
