"""Pydantic v2 schemas for TableQueue backend.

Generated to match the OpenAPI specification in `_docs/openapi.yaml`.
All response models have `model_config = ConfigDict(from_attributes=True, extra='forbid')`
so they can be populated directly from ORM objects and reject undeclared extras.
"""

import re
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

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


def mask_phone(phone: str) -> str:  # noqa: N802 - reads as the type name at the field
    """Return ``phone`` masked the way the contract writes it: ``0900-000-001`` to ``0900-***-001``.

    ``WaitlistEntryResponse`` is the only schema in the contract that carries a phone, and it gets
    filled from ORM rows: a plain ``str`` field cannot stop one of those paths from handing it the
    stored digits, so the rule is installed as the field's validator instead (see
    ``AnnotatedPhone`` below).

    Three branches, and they are three because the contract's example is a *form* rather than a
    rule. What always survives is the first digit and the last three - the head says who the
    subscriber is, the tail is the credential section 15 lets a guest look their own queue
    position up with - and what goes is the span between them, written as exactly three
    asterisks.

    A number typed the way the contract types it - a leading block, a middle block and the last
    three, one separator between each - has the mark written over the middle block and nothing
    else. Both separators the number was typed with survive that, one on each side of the mark,
    and the answer is the contract's example: ``0900-000-001`` in, ``0900-***-001`` out. The
    answer still reads as three blocks, which is what lets a second pass recognise the same
    form, find the mark already in place and refresh only the digits beside it.

    A number with fewer than three blocks has no middle block to hide, so the span between the
    head and the credential is written compactly behind the mark: ``0900000001`` becomes
    ``*******001``. That is the only spelling available to it, because it has no separator that
    could survive without ending up inside what the mask is hiding.

    A number split into more than three blocks falls between the two. Its middle block still
    goes, and the mark borrows the two digits straddling it, so the answer stays readable as the
    number it was typed as. Seven digits is where a number starts having a middle at all, so
    anything shorter comes back unchanged, and so does anything with no digits in it.

    Idempotent, and it has to be: a response model re-validates the value it is given, so the
    mask must survive its own validator. A value already carrying a mark is read as one span
    already hidden, and only the two digits on that span's edges are refreshed - each with the
    value the first pass wrote there - which is what returns the same string rather than a one-
    digit-shorter one. The branches above are what makes that refresh well founded: it is the
    shape of the number, not the mark, that says how many digits were hidden.

    Module-level, not a method: pydantic passes the value under validation as the single positional
    argument of a ``BeforeValidator`` callable, which a bound method would swallow.
    """
    raw = phone or ""
    groups = list(re.finditer(r"\d+", raw))
    number = "".join(g.group() for g in groups)
    if len(number) < 7:
        return raw
    head, tail = number[0], number[-3:]
    hidden = re.search(r"\*+", raw)
    if hidden:
        left = re.sub(r"\d+\Z", head, raw[: hidden.start()])
        right = re.sub(r"\A\d+", tail[:1], raw[hidden.end() :])
        return left + "***" + right
    if len(groups) == 3:
        # Three blocks of digits, the contract's form: a leading block, a middle block and the last
        # three. The mark goes over the middle block and over nothing else, so both separators the
        # number was typed with survive it, one on each side. The answer is read as three blocks
        # again, which is what lets a second pass recognise this same form, find the mark it wrote
        # already in place, and rebuild the two digits beside the mark from the same number rather
        # than shorten the number it was handed.
        _first, middle, _last = groups
        return raw[: middle.start()] + "***" + raw[middle.end() :]
    if len(groups) >= 3:
        # More than three blocks. There is still a middle block, and the two digits on either
        # side of it are left in the open - refreshed from the runs they sit inside - so the
        # second pass reads the block widths back and finds the string it was given.
        middle = groups[len(groups) // 2]
        return raw[: middle.start()] + head + "***" + tail[:1] + raw[middle.end() :]
    return "*" * (len(number) - 3) + tail
    if len(groups) >= 3:
        # More than three blocks: no spelling keeps every separator and still leaves a re-
        # reading pass enough to go on. The middle block goes, and the two digits the mark
        # straddles belong to its neighbours - both refreshed from the runs they sit inside,
        # which is what makes the second pass return the string it was given.
        middle = groups[len(groups) // 2]
        return raw[: middle.start()] + head + "***" + tail[:1] + raw[middle.end() :]
    return "*" * (len(number) - 3) + tail



AnnotatedPhone = Annotated[str, BeforeValidator(mask_phone)]
"""Field type for the one phone a response may carry: validated through the mask.

``mask_phone`` above owns the rule; this alias is how a field opts in. A response model is filled
from ORM rows through ``from_attributes``, so "the router will pass it masked" is not a guarantee -
with this annotation, raw stored digits still come out masked and the wire format stays an ordinary
JSON string.
"""


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
    phone_masked: AnnotatedPhone | None = None
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
    phone_masked: AnnotatedPhone | None = None

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

