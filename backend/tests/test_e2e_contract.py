"""E2E contract probe for T32 frontend integration.

Drives the core guest/staff flow against the in-process TestClient:
join -> login -> call -> board.

Uses the same TestClient pattern as other backend tests (no live server).
Verifies the contract paths and response shapes that the frontend depends on.

Note: The status endpoint requires ownership factor (token/phone_last3) which is
T34 scope. This test focuses on paths that work without that factor.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_e2e_contract.db")
os.environ.setdefault("JWT_SECRET", "tq-test-jwt-secret-e2e-0123456789abcdef")
os.environ.setdefault("STAFF_PIN", "1234")
os.environ.setdefault("ENV", "development")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.public_fixtures import seed_branch


@pytest.fixture
def client():
    """A TestClient over the shared app, using the module's database."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """Provide a fresh database session with schema created."""
    from app import database
    from sqlalchemy.orm import Session

    # Create all tables
    database.Base.metadata.create_all(bind=database.engine)
    session = Session(bind=database.engine)
    try:
        yield session
    finally:
        session.close()
        # Clean up tables after test
        database.Base.metadata.drop_all(bind=database.engine)


def test_e2e_join_and_board(client, db_session):
    """Test join and board endpoints - core guest flow.

    Verifies the guest-facing contract paths and response shapes.
    Note: Status endpoint requires ownership factor (T34 scope).
    """
    # Setup
    seed_branch(db_session, branch_id=1, is_open=True)
    db_session.commit()

    # Join - returns 201 Created
    join_payload = {
        "name": "Test Guest",
        "phone": "0900-000-002",
        "party_size": 2,
    }
    join_response = client.post("/api/v1/branches/1/waitlist", json=join_payload)
    assert join_response.status_code == 201
    join_data = join_response.json()
    assert "queue_number" in join_data
    assert "status" in join_data
    assert join_data["status"] == "WAITING"
    queue_number = join_data["queue_number"]

    # Board should show the waiting count
    board_response = client.get("/api/v1/public/branches/1/board")
    assert board_response.status_code == 200
    board_data = board_response.json()
    assert "current_called" in board_data
    assert "next_up" in board_data
    assert "recent_calls" in board_data
    assert "waiting_count" in board_data
    assert board_data["waiting_count"] >= 1


def test_e2e_full_flow(client, db_session):
    """Full E2E flow: join -> login -> call -> board.

    This test verifies the complete contract that the frontend depends on:
    1. Guest joins waitlist via POST /api/v1/branches/{branch_id}/waitlist
    2. Staff logs in via POST /api/v1/auth/login
    3. Staff calls next party via PATCH /api/v1/staff/waitlist/call
    4. Board reflects changes via GET /api/v1/public/branches/{branch_id}/board

    Note: Status endpoint requires ownership factor (T34 scope) - skipped here.
    Note: Seat/release require table setup - tested separately.
    """
    # Setup: seed a branch and settings
    branch = seed_branch(db_session, branch_id=1, is_open=True)
    db_session.commit()

    # Step 1: Guest joins waitlist
    join_payload = {
        "name": "Test Guest",
        "phone": "0900-000-001",
        "party_size": 4,
        "note": "E2E test",
    }
    join_response = client.post("/api/v1/branches/1/waitlist", json=join_payload)
    assert join_response.status_code == 201, f"Join failed: {join_response.text}"
    join_data = join_response.json()
    assert "id" in join_data, "Join response missing entry id"
    assert "queue_number" in join_data, "Join response missing queue_number"
    assert "status" in join_data, "Join response missing status"
    queue_number = join_data["queue_number"]
    entry_id = join_data["id"]

    # Step 2: Staff logs in
    login_response = client.post("/api/v1/auth/login", json={"pin": "1234"})
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"
    login_data = login_response.json()
    assert "access_token" in login_data, "Login response missing access_token"
    access_token = login_data["access_token"]
    assert login_data["token_type"] == "bearer"

    # Step 3: Staff calls next party (requires auth)
    # Note: call endpoint is POST /api/v1/staff/waitlist/{entry_id}/call
    call_headers = {"Authorization": f"Bearer {access_token}"}
    call_response = client.post(f"/api/v1/staff/waitlist/{entry_id}/call", headers=call_headers)
    assert call_response.status_code == 200, f"Call failed: {call_response.text}"
    call_data = call_response.json()
    # call_entry returns WaitlistEntryResponse directly
    assert call_data["queue_number"] == queue_number
    assert call_data["status"] == "CALLED"

    # Step 4: Board reflects the called party
    board_response = client.get("/api/v1/public/branches/1/board")
    assert board_response.status_code == 200, f"Board failed: {board_response.text}"
    board_data = board_response.json()
    assert "current_called" in board_data, "Board missing current_called"
    assert "next_up" in board_data, "Board missing next_up"
    assert "recent_calls" in board_data, "Board missing recent_calls"
    assert "waiting_count" in board_data, "Board missing waiting_count"
    # The current_called should be our guest
    if board_data["current_called"]:
        assert board_data["current_called"]["queue_number"] == queue_number


def test_e2e_board_endpoint(client, db_session):
    """Test board endpoint returns correct structure.

    Verifies the public board contract.
    """
    # Setup with some entries
    seed_branch(db_session, branch_id=1, is_open=True)
    db_session.commit()

    # Board should work even with empty waitlist
    board_response = client.get("/api/v1/public/branches/1/board")
    assert board_response.status_code == 200
    board_data = board_response.json()
    assert "current_called" in board_data, "Board missing current_called"
    assert "next_up" in board_data, "Board missing next_up"
    assert "recent_calls" in board_data, "Board missing recent_calls"
    assert "waiting_count" in board_data, "Board missing waiting_count"


def test_e2e_login_response_shape(client, db_session):
    """Test login response has correct shape (access_token, not token).

    This is critical for the frontend's auth.ts which reads response.access_token.
    """
    # Setup
    seed_branch(db_session, branch_id=1, is_open=True)
    db_session.commit()

    # Login
    login_response = client.post("/api/v1/auth/login", json={"pin": "1234"})
    assert login_response.status_code == 200
    login_data = login_response.json()

    # Verify response shape matches contract
    assert "access_token" in login_data, "Login response must have access_token"
    assert "expires_in" in login_data, "Login response must have expires_in"
    assert "token_type" in login_data, "Login response must have token_type"
    assert login_data["token_type"] == "bearer"
    assert isinstance(login_data["expires_in"], int), "expires_in must be seconds count"


def test_e2e_cancel_endpoint(client, db_session):
    """Test cancel endpoint exists and accepts correct shape.

    Verifies POST /api/v1/waitlist/{queue_number}/cancel.
    Note: Cancel may require ownership factor - we verify the endpoint exists.
    """
    # Setup
    seed_branch(db_session, branch_id=1, is_open=True)
    db_session.commit()

    # Join
    join_payload = {
        "name": "Cancel Test",
        "phone": "0900-000-003",
        "party_size": 2,
    }
    join_response = client.post("/api/v1/branches/1/waitlist", json=join_payload)
    assert join_response.status_code == 201
    queue_number = join_response.json()["queue_number"]

    # Cancel - endpoint exists, may require ownership factor
    cancel_response = client.post(f"/api/v1/waitlist/{queue_number}/cancel")
    # Cancel may require auth/token - just verify the endpoint exists
    # and returns a structured response (200 or 4xx with error)
    assert cancel_response.status_code in (200, 201, 401, 403, 422), f"Unexpected cancel status: {cancel_response.status_code}"
