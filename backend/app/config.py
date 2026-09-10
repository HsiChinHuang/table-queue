"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
