"""Application configuration using pydantic-settings."""

import os
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Secret material this repository publishes (backend/.env.example, README.md, docs).
# A value listed here is public knowledge, so it can never be a signing credential.
PUBLISHED_JWT_SECRETS: tuple[str, ...] = ("change-me-in-production", "test-secret-key")

# Minimum length for a JWT signing secret, matching `secrets.token_urlsafe(32)` output.
JWT_SECRET_MIN_LENGTH = 32

# The complete set of environments this application recognises (security audit A-3 / D-2, decision
# D-1). The list lives in one place because two consumers read the label - the reset guard in
# `app/routers/admin.py` and the `/health` field in `app/main.py` - and nothing else does now that
# SQL echo answers to its own flag (see `sql_echo` below). A third `if settings.env == ...` would
# re-open exactly the hole this field closes, so anything that asks whether a label is a name this
# program recognises asks this tuple instead of spelling a comparison.
ENVIRONMENTS: tuple[str, ...] = ("development", "test", "production")


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Every required setting is a ``Field(...)`` with no default, so a missing one fails the whole
    construction instead of resolving quietly. ``env`` is one of them, and
    ``_refuse_an_unnamed_environment`` records why that one is checked ahead of field validation
    rather than inside it.
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

    @model_validator(mode="before")
    @classmethod
    def _refuse_an_unnamed_environment(cls, data: Any) -> Any:
        """Refuse a namespace in which ``ENV`` was never named (audit A-3 / D-2, decision D-1).

        This is the *presence* half of the check, and it has to run before field validation rather
        than inside it. Two measured facts fix the shape:

        * pydantic-settings v2 folds ``os.environ`` (and ``.env``) into the same validated namespace
          as constructor kwargs, so on a finished instance a default-applied field and a value that
          came from ``ENV=...`` are indistinguishable. That is why an ``env_explicit``-style
          companion attribute is not the mechanism and nothing may require one.
        * the *absence* of a key is only visible on the raw incoming namespace. Measured at the base
          of this fix: with no ``ENV`` anywhere, ``model_fields_set`` on the finished instance was
          ``['database_url', 'jwt_secret', 'staff_pin']`` - no ``env`` - while exporting
          ``ENV=production`` made it ``['database_url', 'env', 'jwt_secret', 'staff_pin']``. A
          ``field_validator`` cannot see the field it is validating in ``info.data``, so it cannot
          answer "was this ever named?" at all; ``mode="before"`` sees the namespace exactly as the
          caller and the environment left it, which is the only place an absence can be observed.

        The scan is case-insensitive and covers the three sources pydantic-settings folds together
        (init kwargs, ``os.environ``, the loaded ``.env`` files), so naming the environment in any of
        them satisfies the requirement - a ``.env`` that states ``ENV`` is a stated choice, not a
        default, which is what D-1 asks for. A value of ``None`` does not count as a name, so nothing
        can reach the value check without first being named.
        """
        # ``data`` is the namespace the caller and the environment produced, folded together by
        # pydantic-settings before any default is applied: init kwargs, ``os.environ`` and the
        # configured ``.env`` files all reach it, so scanning it alone reaches all three. It is
        # consulted case-insensitively because the loader's own key matching is too, and because a
        # validator that recognised ``ENV`` but not ``env`` would refuse a name the application then
        # honoured - a refusal with no reason in it.
        sources: list[dict] = [data]
        for namespace in sources:
            if not isinstance(namespace, dict):
                continue
            if any(
                str(key).lower() == "env" and value is not None
                for key, value in namespace.items()
            ):
                return data
        raise ValueError(
            "env is required: set ENV to one of "
            + "/".join(ENVIRONMENTS)
            + "; the environment is never resolved implicitly, because the value it used to resolve "
            "to implicitly was the permissive one this issue exists to remove"
        )

    @model_validator(mode="after")
    def _reject_an_environment_that_names_nothing(self) -> "Settings":
        """Refuse an ``ENV`` that is present but names nothing: an empty string is a value, D-1.

        ``Field(...)`` establishes that a value must arrive; it says nothing about a value that
        arrives empty, and ``ENV=`` is precisely that. The message keeps pydantic's own wording for
        an off-list ``Literal`` - it names the field and quotes the accepted values - so a caller
        reads one failure ("that is not a recognised environment") rather than two near-identical
        ones, and both paths raise the same ``ValidationError`` shape family that T10's secret
        quality gate already established for this class.
        """
        if not (self.env or "").strip():
            # The message quotes ENVIRONMENTS rather than restating the sentence, because the
            # allow-list is what a caller has to act on and it must not be spelled twice.
            raise ValueError(
                "env names no environment: an empty value is a value, and it is not one of "
                + "/".join(ENVIRONMENTS)
            )
        return self

    # Authentication
    staff_pin: str = Field(..., description="Staff PIN for authentication")

    # Default branch
    default_branch_id: int = Field(default=1, description="Default branch ID")

    # CORS
    cors_origins: str = Field(
        default="http://localhost:5173", description="CORS allowed origins"
    )

    # Environment. Required, no default: see _refuse_an_unnamed_environment for why absence is
    # refused rather than defaulted, and why the allow-list travels in the type rather than in a
    # comment. The label drives exactly two things - the reset guard and the /health field - and
    # never SQL echo.
    env: Literal["development", "test", "production"] = Field(
        ...,
        description=(
            "Environment name: required, and one of development / test / production; there is no "
            "implicit value"
        ),
    )

    # SQL echo. Deliberately independent of `env` (audit A-3's second half, decision D-3): the label
    # a process reports must never decide whether every bound parameter - guest names and phone
    # numbers included - reaches the process log. Off unless asked for, in every environment, on both
    # engines (app/database.py and app/seed.py).
    sql_echo: bool = Field(
        default=False,
        description="Log every SQL statement and its bound parameters (off unless asked for)",
    )

    # App version
    app_version: str = Field(default="0.1.0", description="Application version")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
