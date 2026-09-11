"""Tests for error handling (B-04)."""

import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import ERROR_CODES, AppError, register_error_handlers

# Helper to load specs error codes for comparison

def load_specs_codes() -> dict[str, int]:
    specs_path = Path(__file__).resolve().parents[2] / "_docs" / "specs.md"
    text = specs_path.read_text(encoding="utf-8")
    m = re.search(r"## 11\. Error Codes(.*?)Error response shape", text, re.S)
    assert m, "Error Codes section not found"
    section = m.group(1)
    pattern = re.compile(r"^([A-Z][A-Z_]+)\s+(\d{3})\s", re.M)
    return {code: int(status) for code, status in pattern.findall(section)}


def test_error_codes_match_specs():
    spec_codes = load_specs_codes()
    assert spec_codes == dict(ERROR_CODES)


def test_app_error_basic():
    err = AppError("WAITLIST_NOT_FOUND")
    assert err.status_code == 404
    payload = err.to_payload()
    assert payload == {"error": {"code": "WAITLIST_NOT_FOUND", "message": "WAITLIST NOT FOUND"}}


def test_app_error_with_details_and_override():
    err = AppError(
        "WAITLIST_CLOSED",
        details={"reason": "paused"},
    )
    # Spec defines 409 for WAITLIST_CLOSED
    assert err.status_code == 409
    payload = err.to_payload()
    assert payload["error"]["details"] == {"reason": "paused"}

    # explicit overrides
    err2 = AppError(
        "TABLE_NOT_FOUND",
        message="No such table",
        status_code=418,
        details={"id": 7},
    )
    assert err2.status_code == 418
    assert err2.message == "No such table"
    assert err2.to_payload()["error"]["details"] == {"id": 7}


def test_handler_app_error():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/probe")
    def probe():
        raise AppError("WAITLIST_DUPLICATE_PHONE", details={"queue_number": "A001"})

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/probe")
    assert resp.status_code == 409
    json = resp.json()
    assert json["error"]["code"] == "WAITLIST_DUPLICATE_PHONE"
    assert json["error"]["details"] == {"queue_number": "A001"}


def test_handler_validation_error():
    from pydantic import BaseModel

    app = FastAPI()
    register_error_handlers(app)

    class ProbeModel(BaseModel):
        pin: str

    @app.post("/probe")
    def probe(body: ProbeModel):
        return body

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/probe", json={})
    assert resp.status_code == 422
    json = resp.json()
    assert json["error"]["code"] == "VALIDATION_ERROR"
    fields = json["error"]["details"]["fields"]
    assert any("pin" in f.get("field", "") for f in fields)


def test_handler_unhandled_exception():
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("SECRET-CANARY-8842")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    json = resp.json()
    assert json["error"]["code"] == "INTERNAL_ERROR"
    # Ensure no leak of original message
    assert "SECRET-CANARY-8842" not in resp.text
    assert "Traceback" not in resp.text
