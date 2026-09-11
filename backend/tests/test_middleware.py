"""Tests for middleware (B-04)."""

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)

def test_request_id_generated_and_echoed():
    first = client.get("/health").headers.get("X-Request-ID")
    second = client.get("/health").headers.get("X-Request-ID")
    assert first and second and first != second
    # validate UUID4
    uuid_obj = uuid.UUID(first)
    assert uuid_obj.version == 4
    # echo supplied
    supplied = client.get(
        "/health", headers={"X-Request-ID": "caller-supplied"}
    ).headers.get("X-Request-ID")
    assert supplied == "caller-supplied"

def test_security_headers_present():
    resp = client.get("/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

def test_cors_allowlist(monkeypatch):
    """CORS allow-list is read from settings.cors_origins (AC-14 contract).

    Settings are lru_cache'd and main.py reads them once at import, so the test
    must clear the cache and re-import main to observe a different allow-list.
    """
    import importlib

    from app.config import get_settings

    monkeypatch.setenv("CORS_ORIGINS", "http://listed.test,http://second.test")
    get_settings.cache_clear()
    import app.main as main_mod

    importlib.reload(main_mod)
    try:
        test_client = TestClient(main_mod.app, raise_server_exceptions=False)
        allow = test_client.options(
            "/health",
            headers={"Origin": "http://listed.test", "Access-Control-Request-Method": "GET"},
        )
        deny = test_client.options(
            "/health",
            headers={"Origin": "http://evil.test", "Access-Control-Request-Method": "GET"},
        )
        assert allow.headers.get("access-control-allow-origin") == "http://listed.test"
        assert deny.headers.get("access-control-allow-origin") is None
    finally:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        get_settings.cache_clear()
        importlib.reload(main_mod)


def test_rate_limit():
    # AC-15 contract: the limiter lives on app.state and SlowAPIMiddleware turns a
    # burst into the 429 error envelope. Build an isolated app so the shared app's
    # limiter counters stay untouched by other tests.
    from fastapi import Request

    # Import the module, not names, so we use whichever app/limiter pair is
    # currently loaded even if an earlier test reloaded app.main.
    import app.main as main_mod

    probe_app = main_mod.app
    limiter = main_mod.limiter

    @probe_app.get("/_probe")
    @limiter.limit("1/minute")
    async def _probe(request: Request):
        return {"ok": True}

    probe_client = TestClient(probe_app, raise_server_exceptions=False)
    resp1 = probe_client.get("/_probe")
    resp2 = probe_client.get("/_probe")
    assert resp1.status_code == 200
    assert resp2.status_code == 429
    body = resp2.json()
    assert body["error"]["code"] == "RATE_LIMITED"
