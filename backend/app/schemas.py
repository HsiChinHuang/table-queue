"""Pydantic v2 schemas for TableQueue backend.

Generated to match the OpenAPI specification in `_docs/openapi.yaml`.
All response models have `model_config = ConfigDict(from_attributes=True, extra='forbid')`
so they can be populated directly from ORM objects and reject undeclared extras.
"""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import models

# ---------------------------------------------------------------------------
# Request schemas (12 total)
# ---------------------------------------------------------------------------

class JoinWaitlistRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=9, max_length=15)
    party_size: int = Field(..., ge=1, le=20)
    note: str | None = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def _trim_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        mobile_pat = re.compile(r"^09\d{2}-?\d{3}-?\d{3}$")
        landline_pat = re.compile(r"^02-?\d{4}-?\d{4}$")
        if not (mobile_pat.match(v) or landline_pat.match(v)):
            raise ValueError("invalid phone format for Taiwan")
        return v


class CancelWaitlistRequest(BaseModel):
    token: str | None = None
    phone_last3: str | None = Field(default=None, min_length=3, max_length=3)


class StaffLoginRequest(BaseModel):
    pin: str = Field(..., pattern=r"^\d{4,6}$")


class ChangePinRequest(BaseModel):
    current_pin: str = Field(..., pattern=r"^\d{4,6}$")
    new_pin: str = Field(..., pattern=r"^\d{4,6}$")
    confirm_new_pin: str = Field(..., pattern=r"^\d{4,6}$")


class SeatWaitlistRequest(BaseModel):
    table_id: str = Field(..., description="UUID of the table")

    @field_validator("table_id", mode="before")
    @classmethod
    def _coerce_table_id(cls, v: Any) -> str:
        return str(v) if v is not None else v


class EditWaitlistRequest(BaseModel):
    party_size: int | None = Field(default=None, ge=1, le=20)
    note: str | None = None


class ReorderWaitlistRequest(BaseModel):
    ordered_ids: list[str]

    @field_validator("ordered_ids", mode="before")
    @classmethod
    def _validate_ordered_ids(cls, v: list[Any]) -> list[str]:
        from uuid import UUID as _UUID
        for item in v:
            try:
                _UUID(str(item))
            except Exception as exc:  # noqa: BLE001
                raise ValueError("ordered_ids must contain valid UUID strings") from exc
        return [str(item) for item in v]


class UpdateTableStatusRequest(BaseModel):
    status: Literal["AVAILABLE", "CLEANING"]


class CreateTableRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=10)
    capacity: int = Field(..., ge=1, le=20)
    section: str | None = Field(default=None, max_length=50)
    sort_order: int | None = None


class UpdateTableRequest(BaseModel):
    label: str | None = None
    capacity: int | None = None
    section: str | None = Field(default=None, max_length=50)
    sort_order: int | None = None
    is_active: bool | None = None


class UpdateSettingsRequest(BaseModel):
    address: str | None = None
    avg_seat_minutes: int | None = Field(default=None, ge=5, le=60)
    branch_name: str | None = None
    close_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    hold_minutes: int | None = Field(default=None, ge=5, le=15)
    is_waitlist_open: bool | None = None
    notification_templates: dict[str, Any] | None = None
    open_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    phone: str | None = None
    queue_prefix: str | None = Field(default=None, pattern=r"^[A-Z]{1,3}$")
    restaurant_name: str | None = None
    sound_enabled_default: bool | None = None


class ResetDataRequest(BaseModel):
    confirm: Literal["RESET"]

# ---------------------------------------------------------------------------
# Response schemas (13 total + ErrorBody)
# ---------------------------------------------------------------------------

class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any]

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ErrorResponse(BaseModel):
    error: ErrorBody

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class WaitlistEntryResponse(BaseModel):
    id: str
    queue_number: str
    full_queue_number: str
    status: models.WaitlistStatus
    party_size: int
    created_at: datetime
    # Optional fields
    updated_at: datetime | None = None
    name: str | None = None
    phone_masked: str | None = None
    note: str | None = None
    source: models.WaitlistSource | None = None
    cancelled_reason: models.CancelledReason | None = None
    called_at: datetime | None = None
    seated_at: datetime | None = None
    remaining_seconds: int | None = None
    hold_minutes_snapshot: int | None = None
    table_id: str | None = None
    table_label: str | None = None
    status_token: str | None = None
    status_url: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, v: Any) -> str:
        return str(v) if v is not None else v

    @field_validator("table_id", mode="before")
    @classmethod
    def _coerce_table_id(cls, v: Any) -> str:
        return str(v) if v is not None else v


class WaitlistListResponse(BaseModel):
    items: list[WaitlistEntryResponse]
    total: int

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class WaitlistStatusResponse(BaseModel):
    queue_number: str
    status: models.WaitlistStatus
    party_size: int
    created_at: datetime
    waiting_ahead: int | None = None
    estimated_wait_minutes: int | None = None
    called_at: datetime | None = None
    remaining_seconds: int | None = None
    hold_minutes: int | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class TableResponse(BaseModel):
    id: str
    label: str
    capacity: int
    status: models.TableStatus
    is_active: bool
    section: str | None = None
    sort_order: int | None = None
    current_waitlist: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id(cls, v: Any) -> str:
        return str(v) if v is not None else v


class TableListResponse(BaseModel):
    items: list[TableResponse]
    total: int

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class DashboardResponse(BaseModel):
    waiting_count: int
    called_count: int
    seated_count: int
    available_table_count: int
    occupied_table_count: int
    cleaning_table_count: int
    no_show_today: int | None = None
    cancelled_today: int | None = None
    seated_today: int | None = None
    avg_wait_minutes_today: int | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class SettingsResponse(BaseModel):
    address: str | None = None
    avg_seat_minutes: int
    branch_name: str
    close_time: str | None = None
    has_pin: bool | None = None
    hold_minutes: int
    is_waitlist_open: bool
    notification_templates: dict[str, Any] | None = None
    open_time: str | None = None
    phone: str | None = None
    queue_prefix: str
    restaurant_name: str
    sound_enabled_default: bool | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class PublicBranchResponse(BaseModel):
    address: str | None = None
    branch_name: str
    close_time: str | None = None
    hours: str | None = None
    is_waitlist_open: bool
    open_time: str | None = None
    phone: str | None = None
    restaurant_name: str
    timezone: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class BoardResponse(BaseModel):
    branch_name: str
    hours: str | None = None
    is_waitlist_open: bool
    restaurant_name: str
    waiting_count: int
    current_called: dict[str, Any] | None = None
    next_up: dict[str, Any] | None = None
    recent_calls: list[dict[str, Any]] | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class HealthResponse(BaseModel):
    env: str
    status: str
    version: str

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class StaffLoginResponse(BaseModel):
    access_token: str
    expires_in: int
    token_type: str

    model_config = ConfigDict(from_attributes=True, extra="forbid")

