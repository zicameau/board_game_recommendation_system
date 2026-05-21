"""Application settings.

All runtime configuration lives in a single `Settings` Pydantic model loaded once from
`.env.local`. Code should import the singleton:

    from app.config import settings
    settings.MODEL_VERSION

Setup of `.env.local` is documented in `docs/local-development.md`; `.env.example` is the
template.

Operationally the most important values are `DATABASE_URL` (Postgres / Supabase pooler),
`MODEL_BUNDLE_PATH` + `MODEL_VERSION` (which bundle to serve), `AUTH_MODE` (`supabase` vs
`dev_shim`), and the `SUPABASE_*` keys.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed environment-backed settings; instantiated once as the module-level `settings`."""

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: Literal["local", "staging", "prod"] = "local"
    AUTH_MODE: Literal["supabase", "dev_shim"] = "supabase"

    # 127.0.0.1 + port 5433 match docker-compose (host maps 5433 -> container 5432).
    DATABASE_URL: str = "postgresql://bgg:bgg@127.0.0.1:5433/bgg_dev"
    # Optional: direct URL for Alembic when different from pooler
    ALEMBIC_DATABASE_URL: str | None = None

    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_ANON_KEY", "SUPABASE_KEY"),
    )
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_JWT_SECRET: str | None = None

    API_BASE_URL: str = "http://localhost:8000"
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:8000"])

    SECURE_COOKIES: bool = False
    SESSION_SECRET: str = "dev-change-me"

    MODEL_BUNDLE_PATH: str = "bundles"
    MODEL_VERSION: str = "popularity-v1-fixture"

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    ACCESS_COOKIE_NAME: str = "bgg_access"
    REFRESH_COOKIE_NAME: str = "bgg_refresh"

    @computed_field
    @property
    def model_bundle_dir(self) -> str:
        """Path to the active bundle directory (`MODEL_BUNDLE_PATH/MODEL_VERSION`)."""
        from pathlib import Path

        return str(Path(self.MODEL_BUNDLE_PATH) / self.MODEL_VERSION)


settings = Settings()
