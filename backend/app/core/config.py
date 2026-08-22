import secrets
import warnings
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    FASTAPI_ENV: Literal["development"] | None = None
    ENVIRONMENT: Literal["local", "staging", "production"] | None = "local"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_development(self) -> bool:
        return self.FASTAPI_ENV == "development" or self.ENVIRONMENT == "local"

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None

    DATABASE_URL: PostgresDsn | None = None
    POSTGRES_SERVER: str | None = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str | None = "postgres"
    POSTGRES_PASSWORD: str = "changethis"
    POSTGRES_DB: str = "app"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _ensure_psycopg_driver(cls, v: Any) -> Any:
        if isinstance(v, str):
            database_url = v
        elif isinstance(v, PostgresDsn):
            database_url = str(v)
        else:
            return v

        schemes = ["postgresql://", "postgres://", "postgresql+asyncpg://"]
        for scheme in schemes:
            if database_url.startswith(scheme):
                return database_url.replace(scheme, "postgresql+psycopg://", 1)
        return database_url

    @model_validator(mode="after")
    def _ensure_database_url(self) -> Self:
        if self.DATABASE_URL is None:
            if not self.POSTGRES_SERVER or not self.POSTGRES_USER:
                self.DATABASE_URL = PostgresDsn(
                    f"postgresql+psycopg://postgres:changethis@localhost:5432/{self.POSTGRES_DB}"
                )
            else:
                self.DATABASE_URL = PostgresDsn.build(
                    scheme="postgresql+psycopg",
                    username=self.POSTGRES_USER,
                    password=self.POSTGRES_PASSWORD,
                    host=self.POSTGRES_SERVER,
                    port=self.POSTGRES_PORT,
                    path=self.POSTGRES_DB,
                )
        elif (
            self.POSTGRES_DB != "app"
            and self.DATABASE_URL.path
            and self.DATABASE_URL.path.lstrip("/") != self.POSTGRES_DB
        ):
            hosts = self.DATABASE_URL.hosts()
            first_host = hosts[0] if hosts else None
            username = (
                first_host.get("username")
                if first_host
                else self.POSTGRES_USER or "postgres"
            )
            password = (
                first_host.get("password") if first_host else self.POSTGRES_PASSWORD
            )
            host = (
                first_host.get("host")
                if first_host
                else self.POSTGRES_SERVER or "localhost"
            )
            port = first_host.get("port") if first_host else self.POSTGRES_PORT or 5432
            self.DATABASE_URL = PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=username,
                password=password,
                host=host,
                port=port,
                path=self.POSTGRES_DB,
            )
        else:
            if self.DATABASE_URL.path:
                self.POSTGRES_DB = self.DATABASE_URL.path.lstrip("/")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        assert self.DATABASE_URL is not None
        return self.DATABASE_URL

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.is_development:
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        if self.DATABASE_URL:
            for host in self.DATABASE_URL.hosts():
                if host.get("password") == "changethis":
                    self._check_default_secret("DATABASE_URL password", "changethis")
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


settings = Settings()  # type: ignore
