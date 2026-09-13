"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Secret material this repository publishes (backend/.env.example, README.md, docs).
# A value listed here is public knowledge, so it can never be a signing credential.
PUBLISHED_JWT_SECRETS: tuple[str, ...] = ("change-me-in-production", "test-secret-key")

# Minimum length for a JWT signing secret, matching `secrets.token_urlsafe(32)` output.
JWT_SECRET_MIN_LENGTH = 32


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All required settings use Field with default=... to fail fast if missing.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = Field(..., description="Database connection URL")

    # JWT
    jwt_secret: str = Field(..., description="JWT signing secret key")
    jwt_expire_hours: int = Field(default=12, description="JWT token expiration in hours")

    @field_validator("jwt_secret")
    @classmethod
    def _reject_weak_jwt_secret(cls, value: str) -> str:
        """Fail closed on a secret an attacker could know (security audit A-1 / D-1).

        The gate applies in every environment and carries no bypass flag, exactly like
        the ``Field(...)`` requirement for a missing ``JWT_SECRET``: a weak value stops
        the process at construction instead of booting and minting forgeable staff
        tokens. It refuses three things - a value that is empty after stripping, one of
        the published example literals, and anything under the length floor.
        """
        secret = value.strip() if isinstance(value, str) else ""
        if not secret:
            raise ValueError(
                "jwt_secret is empty: set JWT_SECRET to a generated secret of at "
                "least 32 characters "
                '(python -c "import secrets; print(secrets.token_urlsafe(32))"), '
                "never a known example value"
            )
        if secret in PUBLISHED_JWT_SECRETS:
            raise ValueError(
                "jwt_secret is one of the known example secrets this repo publishes; "
                "use a private generated value of at least 32 characters"
            )
        if len(secret) < JWT_SECRET_MIN_LENGTH:
            raise ValueError(
                "jwt_secret is too short: at least 32 characters are required; a known "
                "example or otherwise published value is never accepted"
            )
        return secret

    # Authentication
    staff_pin: str = Field(..., description="Staff PIN for authentication")

    # Default branch
    default_branch_id: int = Field(default=1, description="Default branch ID")

    # CORS
    cors_origins: str = Field(
        default="http://localhost:5173", description="CORS allowed origins"
    )

    # Environment
    env: str = Field(default="development", description="Environment name")

    # App version
    app_version: str = Field(default="0.1.0", description="Application version")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
