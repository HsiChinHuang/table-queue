"""Tests for Pydantic schemas matching the OpenAPI spec.

Covers request validation, response model configuration, enum wiring, and
ORM model validation (model_validate)."""

import os
import sys
from typing import get_args

import pytest
from pydantic import ValidationError

# Ensure the backend package is importable
sys.path.insert(0, "backend")
from app import models, schemas

# ---------- Request schema tests ----------

def test_join_waitlist_valid_and_trim():
    payload = {"name": "  Alice  ", "phone": "0912-345-678", "party_size": 2}
    model = schemas.JoinWaitlistRequest(**payload)
    assert model.name == "Alice"
    assert model.phone == "0912-345-678"

def test_join_waitlist_invalid_name():
    with pytest.raises(ValidationError):
        schemas.JoinWaitlistRequest(name="", phone="0912-345-678", party_size=2)
    with pytest.raises(ValidationError):
        schemas.JoinWaitlistRequest(name="x" * 51, phone="0912-345-678", party_size=2)

def test_join_waitlist_invalid_phone():
    base = {"name": "Bob", "party_size": 3}
    bad_phones = ["0912345", "0812-345-678", "0912-ABC-678"]
    for p in bad_phones:
        with pytest.raises(ValidationError):
            schemas.JoinWaitlistRequest(**{**base, "phone": p})
    m = schemas.JoinWaitlistRequest(**{**base, "phone": "02-1234-5678"})
    assert m.phone == "02-1234-5678"

def test_join_waitlist_party_size_bounds():
    base = {"name": "Bob", "phone": "0912-345-678"}
    with pytest.raises(ValidationError):
        schemas.JoinWaitlistRequest(**{**base, "party_size": 0})
    with pytest.raises(ValidationError):
        schemas.JoinWaitlistRequest(**{**base, "party_size": 21})
    schemas.JoinWaitlistRequest(**{**base, "party_size": 1})
    schemas.JoinWaitlistRequest(**{**base, "party_size": 20})

def test_join_waitlist_note_length():
    base = {"name": "Bob", "phone": "0912-345-678", "party_size": 2}
    schemas.JoinWaitlistRequest(**{**base, "note": "x" * 200})
    with pytest.raises(ValidationError):
        schemas.JoinWaitlistRequest(**{**base, "note": "x" * 201})

def test_pin_fields():
    schemas.StaffLoginRequest(pin="1234")
    schemas.StaffLoginRequest(pin="123456")
    for bad in ["123", "1234567", "12a4"]:
        with pytest.raises(ValidationError):
            schemas.StaffLoginRequest(pin=bad)
    with pytest.raises(ValidationError):
        schemas.ChangePinRequest(current_pin="1234", new_pin="5678")
    schemas.ChangePinRequest(current_pin="1234", new_pin="5678", confirm_new_pin="5678")
    with pytest.raises(ValidationError):
        schemas.ChangePinRequest(current_pin="1234", new_pin="abc", confirm_new_pin="abc")

def test_table_requests():
    schemas.CreateTableRequest(label="A5", capacity=2)
    with pytest.raises(ValidationError):
        schemas.CreateTableRequest(label="", capacity=2)
    with pytest.raises(ValidationError):
        schemas.CreateTableRequest(label="A" * 11, capacity=2)
    with pytest.raises(ValidationError):
        schemas.CreateTableRequest(label="A5", capacity=0)
    with pytest.raises(ValidationError):
        schemas.CreateTableRequest(label="A5", capacity=21)
    with pytest.raises(ValidationError):
        schemas.CreateTableRequest(label="A5", capacity=2, section="s" * 51)
    schemas.UpdateTableStatusRequest(status="AVAILABLE")
    schemas.UpdateTableStatusRequest(status="CLEANING")
    with pytest.raises(ValidationError):
        schemas.UpdateTableStatusRequest(status="OCCUPIED")
    with pytest.raises(ValidationError):
        schemas.UpdateTableStatusRequest(status="OPEN")

def test_settings_bounds_and_patterns():
    schemas.UpdateSettingsRequest()
    schemas.UpdateSettingsRequest(hold_minutes=5)
    schemas.UpdateSettingsRequest(hold_minutes=15)
    for v in [4, 16]:
        with pytest.raises(ValidationError):
            schemas.UpdateSettingsRequest(hold_minutes=v)
    schemas.UpdateSettingsRequest(avg_seat_minutes=5)
    schemas.UpdateSettingsRequest(avg_seat_minutes=60)
    for v in [4, 61]:
        with pytest.raises(ValidationError):
            schemas.UpdateSettingsRequest(avg_seat_minutes=v)
    schemas.UpdateSettingsRequest(queue_prefix="A")
    schemas.UpdateSettingsRequest(queue_prefix="ABC")
    for v in ["ABCD", "ab", "A1"]:
        with pytest.raises(ValidationError):
            schemas.UpdateSettingsRequest(queue_prefix=v)
    schemas.UpdateSettingsRequest(open_time="11:30")
    with pytest.raises(ValidationError):
        schemas.UpdateSettingsRequest(open_time="9:30")
    with pytest.raises(ValidationError):
        schemas.UpdateSettingsRequest(close_time="noon")

def test_reset_data_confirm():
    schemas.ResetDataRequest(confirm="RESET")
    with pytest.raises(ValidationError):
        schemas.ResetDataRequest(confirm="WRONG")

def test_reorder_waitlist():
    schemas.ReorderWaitlistRequest(
        ordered_ids=["5f7c1a9e-9a7b-4f1e-8e1a-1b2c3d4e5f60"]
    )
    with pytest.raises(ValidationError):
        schemas.ReorderWaitlistRequest(ordered_ids=["not-a-uuid"])

def test_seat_waitlist_request_uuid_format():
    schemas.SeatWaitlistRequest(table_id="9c1b2d3e-4f5a-6b7c-8d9e-0f1a2b3c4d5e")

# ---------- Response schema config tests ----------

def test_response_models_from_attributes_and_extra_forbid():
    for model in [
        schemas.WaitlistEntryResponse,
        schemas.WaitlistListResponse,
        schemas.WaitlistStatusResponse,
        schemas.TableResponse,
        schemas.TableListResponse,
        schemas.DashboardResponse,
        schemas.SettingsResponse,
        schemas.PublicBranchResponse,
        schemas.BoardResponse,
        schemas.HealthResponse,
        schemas.StaffLoginResponse,
        schemas.ErrorResponse,
    ]:
        cfg = getattr(model, "model_config", {})
        assert cfg.get("from_attributes") is True, f"{model.__name__} missing from_attributes"
        if model is not schemas.ErrorResponse:
            assert cfg.get("extra") == "forbid", f"{model.__name__} extra not forbid"

def _underlying(ann):
    """Unwrap Optional[X] -> X (same rule AC-12 applies to model_fields)."""
    for arg in get_args(ann):
        if arg is not type(None):
            return arg
    return ann


def test_enum_wiring_in_responses():
    fields = schemas.WaitlistEntryResponse.model_fields
    assert _underlying(fields["status"].annotation) is models.WaitlistStatus
    assert (
        _underlying(schemas.TableResponse.model_fields["status"].annotation)
        is models.TableStatus
    )
    # source/cancelled_reason are Optional: a WAITING ORM row has
    # cancelled_reason = NULL and must still validate (AC-13).
    assert _underlying(fields["source"].annotation) is models.WaitlistSource
    assert _underlying(fields["cancelled_reason"].annotation) is models.CancelledReason

# ---------- ORM model validation tests ----------

def test_orm_row_validation(db_session):
    restaurant = models.Restaurant(name="R")
    db_session.add(restaurant)
    db_session.flush()
    branch = models.Branch(
        restaurant_id=restaurant.id,
        name="B",
        address="Addr",
        phone="02-1234-5678",
        open_time="11:00",
        close_time="21:00",
    )
    db_session.add(branch)
    db_session.flush()
    table = models.Table(
        branch_id=branch.id,
        label="A1",
        capacity=2,
        sort_order=1,
    )
    db_session.add(table)
    db_session.flush()
    entry = models.WaitlistEntry(
        branch_id=branch.id,
        queue_number="A001",
        full_queue_number="A-20260911-001",
        queue_prefix="A",
        seq=1,
        business_date="2026-09-11",
        name="Alice",
        phone="0912345678",
        party_size=2,
        sort_order=1,
        status=models.WaitlistStatus.WAITING,
        source=models.WaitlistSource.CUSTOMER,
    )
    db_session.add_all([table, entry])
    db_session.commit()
    t_res = schemas.TableResponse.model_validate(table)
    assert t_res.label == "A1" and t_res.capacity == 2
    w_res = schemas.WaitlistEntryResponse.model_validate(entry)
    assert w_res.queue_number == "A001"
    dash = schemas.DashboardResponse(
        waiting_count=1,
        called_count=0,
        seated_count=0,
        available_table_count=1,
        occupied_table_count=0,
        cleaning_table_count=0,
        no_show_today=0,
        cancelled_today=0,
        seated_today=0,
        avg_wait_minutes_today=0,
    )
    assert dash.waiting_count == 1

# ---------- Fixtures for ORM tests ----------
os.environ.setdefault('DATABASE_URL', 'sqlite:///./test.db')
os.environ.setdefault('JWT_SECRET', 'test')
os.environ.setdefault('STAFF_PIN', '0000')

@pytest.fixture(scope='module')
def db_engine(tmp_path_factory):
    db_path = tmp_path_factory.mktemp('db') / 'test.db'
    from app.database import Base, engine
    engine.dispose()
    engine.url = f"sqlite:///{db_path}"
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(db_engine):
    from app.database import SessionLocal
    sess = SessionLocal()
    yield sess
    sess.close()
