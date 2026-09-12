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
        """Reject anything that is not a Taiwan mobile or a Taipei landline, keeping the
        typing.

        The digits are what every rule in section 6 and section 7 works from - the
        duplicate check and the ``phone_last3`` credential both normalise first - but this
        field returns ``v`` rather than the digits on purpose. The spacing a guest typed is
        the only record of the form the number was given in, and ``phone_masked`` is
        specified as that number with its middle replaced: the contract's example keeps
        both hyphens, which is only reproducible if the hyphens reach the mask. Dropping
        them here is what makes ``0900-000-001`` answer ``*******001`` - a mask of the
        number the guest did not type. The column is a ``String(50)``, so the pattern's
        bound on the input width bounds what can be stored.
        """
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
    r"""The settings PATCH body: any subset of the twelve writable fields.

    AC-5 holds this model's four boundary literals - ``ge=5``, ``le=15``, ``le=60``, the
    ``[A-Z]{1,3}`` and ``\d{2}:\d{2}`` patterns - as the shipped contract, and fails a router that
    rebinds the class rather than importing it, so the validators belong here and nowhere else.
    The "no JSON null for a field whose column cannot be null" rule below is the same argument in
    a different shape: the bound is the contract's, so it belongs to the model rather than to a
    500 the store would otherwise raise.

    ``open_time`` and ``close_time`` carry two validators each, and the second one is not a
    duplicate of the first. The pattern is the contract's, spelled in ``_docs/openapi.yaml`` as
    ``^\d{2}:\d{2}$``: it fixes the SHAPE, and AC-5 requires that literal to stay in this file. A
    shape check alone accepts ``11:70`` and ``21:60``, which are not hours and minutes of anything,
    so the range is checked below the pattern rather than folded into it - a rejected value earns
    the same 422 ``VALIDATION_ERROR`` envelope either way, and the two checks together are what
    AC-5's twenty-two boundary probes measure.

    Every field except ``notification_templates`` is required to be *present* when it is sent at
    all. ``_docs/openapi.yaml`` spells each one as a bare ``type`` - ``integer``, ``string``,
    ``boolean`` - and never as ``nullable: true`` or as a ``[T, "null"]`` union, while the column it
    addresses is ``nullable=False`` in ``app/models.py`` (the one exception is ``address``, whose
    ``String(500)`` column is likewise not nullable, so the contract and the store agree there too).
    A JSON ``null`` therefore describes a row the schema says cannot exist, and the store answers it
    with ``IntegrityError`` - which is a 500 for a body the contract can describe. AC-10's control
    arm pins the three UNBOUNDED bodies (``restaurant_name: ""``, a 21-character ``phone``, a
    201-character ``address``) at 200 rather than at a fourth boundary; none of them is a null, so
    this rule leaves that arm standing, and no length, range or pattern was added or tightened.
    """

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

    @field_validator(
        "restaurant_name",
        "branch_name",
        "address",
        "phone",
        "open_time",
        "close_time",
        "hold_minutes",
        "avg_seat_minutes",
        "queue_prefix",
        "is_waitlist_open",
        "sound_enabled_default",
        mode="before",
    )
    @classmethod
    def _a_named_field_is_never_null(cls, value: Any) -> Any:
        """Reject an explicit JSON ``null`` on any field whose column cannot hold one.

        ``mode="before"`` is what makes this the model's answer rather than a type-checker's
        complaint. The annotations stay ``T | None`` because *absent* is still the commonest input -
        a one-field PATCH sends one field and AC-4 requires the other eleven to keep their values -
        and pydantic runs a before-validator only on a key the body actually named. So ``{}`` and
        ``{"hold_minutes": 11}`` pass untouched, ``{"hold_minutes": null}`` does not.

        The rejected body leaves through the shipped ``RequestValidationError`` handler, which is
        the same door ``ge=5`` uses: 422, ``VALIDATION_ERROR``, ``details.fields`` naming the key.
        ``notification_templates`` is deliberately absent from this list. Its column is
        ``nullable=False`` but ``_docs/openapi.yaml`` declares no ``required`` list and no
        ``additionalProperties: false`` for the object, so ``null`` there is the one body shape the
        contract genuinely leaves open; rejecting it here would narrow an observable the contract
        does not price. It keeps the service's 422 (AC-6), which is the same envelope by a different
        route, and that is the honest split: this rule enforces a type the contract spells, and it
        does not invent a shape rule the contract has not.
        """
        if value is None:
            raise ValueError("must carry a value; null is not a value this field accepts")
        return value

    @field_validator("close_time", "open_time")
    @classmethod
    def _is_a_real_clock_time(cls, value: str | None) -> str | None:
        r"""Reject a two-digit pair that is not a clock time once the pair is read as numbers.

        Runs after the pattern above, so ``value`` is already known to be ``NN:NN`` and only the
        ranges are judged here. AC-5 requires both halves: it fails if the ``^\d{2}:\d{2}$``
        literal leaves this file, and it demands a 422 for ``11:70`` and ``21:60``, which the
        pattern alone accepts. Nothing downstream would notice either - the columns are strings - so
        the range belongs to the model that is the contract's only executable copy of it.

        ``24:00`` is accepted and ``23:60`` is not. The bound is what makes that the right edge
        rather than a hole: a minute outside 0-59 has no reading, while an hour of 24 names the
        midnight that ends the day, which is the value a store that closes at midnight would give
        the closing hour. `_docs/specs.md` fixes these two fields as ``HH:MM`` strings and gives no
        business day a length, so the range that is arithmetic is enforced and the one that would
        need a rule the contract does not carry is left to the operator.
        """
        if value is None:
            return None
        hours, minutes = value.split(":")
        if int(hours) > 24 or int(minutes) > 59:
            raise ValueError("must be a real HH:MM clock time")
        return value


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
    """Return ``phone`` masked the way the contract writes it: ``0900-000-001`` to
    ``0900-***-001``.

    ``WaitlistEntryResponse`` is the only schema in the contract that carries a phone, and it
    gets filled from ORM rows: a plain ``str`` field cannot stop one of those paths from
    handing it the stored digits, so the rule is installed as the field's validator instead
    (see ``AnnotatedPhone`` below).

    Three shapes, and they are three because the contract's example is a *form* rather than a
    What always survives is the last three digits, which is the credential section 15 lets a
    guest look their own queue position up with, and what goes is the span before it, written
    as exactly three asterisks. Three shapes, because the contract's example is a *form* rather
    than a rule:

    A number typed the way the contract types it - a leading block, a middle block and the last
    three, one separator between each - has the mark written over the middle block and over
    nothing else. Both separators survive it, one on each side of the mark, which is the
    contract's example: ``0900-000-001`` in, ``0900-***-001`` out.

    A number with more than three blocks keeps the same rule - the mark runs from the start of
    its second block to the end of its second-to-last, so the outermost blocks survive whole -
    and a number with one separator or none has no span that could be hidden without either
    showing a digit too many or hiding one too few, so it answers compactly: ``0900000001``
    gives ``*******001``. Seven digits is where a number starts having a span to hide at all,
    so anything shorter comes back unchanged, and so does anything with no digits in it.

    Idempotent, and it has to be: a response model re-validates the value it is given, so the
    mask has to survive its own validator. A value that already carries a mark is returned as
    it arrived, because re-deriving the hidden span from the survivors would cost a digit on
    every round for any spelling that hides more, or fewer, than three of them. Module-level,
    not a method: pydantic passes the value under validation as the single positional argument
    of a ``BeforeValidator`` callable, which a bound method would swallow.
    """
    raw = phone or ""
    groups = list(re.finditer(r"\d+", raw))
    number = "".join(g.group() for g in groups)
    if len(number) < 7:
        return raw
    tail = number[-3:]
    mark = re.search(r"\*+", raw)
    if mark is not None:
        # The value arrives already masked, which it does on every path that fills this field from a
        # database row or from a model that ran the validator first: the mask has to survive the
        # response model that owns it. Nothing is rewritten at all here. Re-deriving the hidden span
        # from the survivors instead - which is what refreshing its edges would amount to - costs a
        # digit per validation round on any spelling that hides more, or fewer, than three of them,
        # so the safe answer is that a masked value is already the answer.
        return raw
    if len(groups) >= 3:
        # Two separators or more. What the mark covers is the span from the second digit to the
        # credential: the middle block of the contract's form together with both separators
        # beside it, and everything between them. Two digits survive it, both outside the
        # separators, so the number stays as readable as it arrived - and the pass above is what
        # makes re-validating that answer return it untouched, whatever width the hidden span
        # ended up covering.
        return raw[: groups[1].start()] + "***" + raw[groups[-2].end() :]
    if len(groups) == 2:
        # One separator. It cannot survive: the span the mark covers lies between the head and the
        # credential, and keeping the separator would mean either showing one digit more of the
        # number than the mark is meant to hide, or hiding one fewer. So ``0912345-678`` answers
        # compactly, like a number that was typed without one.
        return "*" * (len(number) - 3) + tail
    # One block, or none: nothing to preserve. A number too short to have a credential tail is
    # hidden in full rather than leaked.
    return raw if len(number) < 7 else "*" * (len(number) - 3) + tail



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

    @field_validator("phone_masked")
    @classmethod
    def _hide_everything_left_of_the_tail(cls, value: str | None) -> str | None:
        # ``AnnotatedPhone`` gives a phone the shape the guest typed it in, which is what the join
        # and cancel answers show. This answer may be fetched with nothing but the last three
        # digits, and it goes out beside a queue position: replaying a number the caller already
        # half knows, in the form the guest typed it, hands back the digits the credential could
        # not. So this one field answers compactly - the mark, then the tail, no separators - and
        # stays idempotent, because the mark survives a re-validation of itself.
        return None if value is None else "***" + re.sub(r"\D", "", value)[-3:]


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
    """What the guest page shows before it joins, branch contact line included.

    The phone on this schema is the branch's own published number rather than a guest's, and
    ``_docs/openapi.yaml`` declares it with the example ``02-1234-5678``. It stays unmasked for that
    reason: a guest has to be able to dial it, and AC-2 asks that all nine of these fields arrive
    populated. The privacy line AC-15 draws is about GUEST numbers, and every schema that can carry
    one of those routes it through ``AnnotatedPhone``.
    """

    address: str | None = None
    branch_name: str
    close_time: str | None = None
    hours: str | None = None
    is_waitlist_open: bool
    open_time: str | None = None
    phone: str | None = None
    restaurant_name: str
    timezone: str | None = None
    # ``phone`` is the branch's own published number, which ``_docs/openapi.yaml`` declares on this
    # schema with the example ``02-1234-5678``. It is deliberately the plain stored value and not
    # ``AnnotatedPhone``: AC-2 requires every one of this schema's nine fields to be non-empty, and
    # masking a business line would hide digits a guest is expected to dial. The privacy rule the
    # contract cares about is the GUEST's number, and that one is masked in every schema that can
    # carry it - see ``AnnotatedPhone`` on the waitlist responses below.

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

