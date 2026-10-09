"""Tests for middleware (B-04).

The CORS case is a cross-process check. Settings are ``lru_cache``'d and ``app.main`` reads
them once at import, so observing a non-default allow-list means importing ``app.main`` again
with ``CORS_ORIGINS`` in the environment. That import must happen in another process: the
alternative, ``importlib.reload(app.main)``, hands the rest of the suite a brand-new ``app``
and ``limiter`` while every module imported earlier still holds the old objects (see
``_docs/issues/B-17.md`` for the measured chain). B-04 AC-14 already uses this subprocess
pattern; ``_CORS_PROBE`` is its body.

``pytest.importorskip`` is absent on purpose - a skipped subprocess would let a broken
allow-list pass this file silently, and it is ``subprocess.run`` that reports a missing
interpreter.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path

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

_CORS_PROBE = """
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])

from fastapi.testclient import TestClient
from app.main import app

probe = TestClient(app, raise_server_exceptions=False)
listed = "http://listed.test"
headers = {"Origin": listed, "Access-Control-Request-Method": "GET"}
allow = probe.options("/health", headers=headers)
deny = probe.options("/health", headers=dict(headers, Origin="http://evil.test"))
print(allow.headers.get("access-control-allow-origin"))
print(deny.headers.get("access-control-allow-origin"))
"""


def test_cors_allowlist():
    """The allow-list comes from settings.cors_origins, read once at import (AC-14 contract).

    Observed in a subprocess (B-04 AC-14's pattern) rather than by reloading ``app.main`` in
    this process. A reload constructs a second ``app`` / ``limiter`` pair: modules imported
    earlier keep the pair they bound at import time, and ``tests/conftest.py``'s autouse
    ``disable_limiter`` fixture restores its saved flag onto the object it grabbed at session
    start - not onto whichever instance is current at teardown. A reload here therefore left
    the live limiter switched off for every later test in the run, and the budget tests
    downstream failed on a 200 where they expect a 429. A subprocess cannot touch this
    process's objects, which is the whole point of the isolation this file is about.
    """
    env = dict(os.environ, CORS_ORIGINS="http://listed.test,http://second.test")
    env.setdefault("DATABASE_URL", "sqlite:////tmp/_b17_cors_probe.db")
    backend_dir = str(Path(__file__).resolve().parent.parent)
    probe = subprocess.run(
        [sys.executable, "-c", _CORS_PROBE, backend_dir],
        capture_output=True,
        text=True,
        cwd=backend_dir,
        env=env,
    )
    lines = probe.stdout.strip().splitlines()
    detail = f"rc={probe.returncode} err={probe.stderr[-400:]}"
    assert len(lines) == 2, f"the CORS probe produced no verdict: {detail}"
    allow_origin, deny_origin = lines
    assert allow_origin == "http://listed.test"
    assert deny_origin == "None"


def test_rate_limit():
    # AC-15 contract: the limiter lives on app.state and SlowAPIMiddleware turns a
    # burst into the 429 error envelope. Build an isolated app so the shared app's
    # limiter counters stay untouched by other tests.
    from fastapi import Request

    # Import the module, not names, so this runs against the app/limiter pair the rest of
    # the suite shares. The AC-14 reload used to sit in test_cors_allowlist and reached
    # this test through a freshly built pair, whose limiter is enabled at construction;
    # with the reload gone (B-17) the shared instance is the one tests/conftest.py's
    # autouse ``disable_limiter`` fixture switched off, so a budget test says so out loud
    # and puts the flag back. Same reasoning as B-06's ``limiter_enabled`` fixture.
    import app.main as main_mod

    probe_app = main_mod.app
    limiter = main_mod.limiter
    previous_enabled = limiter.enabled
    limiter.enabled = True
    # The probe route is this test's, not the application's: remember where the shared route
    # table ends and cut everything past that on the way out, so a module that runs later
    # (AC-10's route walk in test_admin_reset) cannot see a route the live application does
    # not declare.
    routes_before = len(probe_app.router.routes)
    try:
        @probe_app.get("/_probe")
        @limiter.limit("1/minute")
        async def _probe(request: Request):
            return {"ok": True}

        probe_client = TestClient(probe_app, raise_server_exceptions=False)
        resp1 = probe_client.get("/_probe")
        resp2 = probe_client.get("/_probe")
        try:
            assert resp1.status_code == 200
            assert resp2.status_code == 429
            body = resp2.json()
            assert body["error"]["code"] == "RATE_LIMITED"
        finally:
            limiter.enabled = previous_enabled
    finally:
        del probe_app.router.routes[routes_before:]


def _add_probe_route(path: str, handler):
    """Append ``handler`` at ``path`` on the shared app; return the cut point for cleanup.

    The probe route is the test's, not the application's: remember where the shared route
    table ends and cut everything past it in the caller's ``finally``, the same way
    ``test_rate_limit`` does, so no later test can see a route the live application does
    not declare.
    """
    import app.main as main_mod

    probe_app = main_mod.app
    routes_before = len(probe_app.router.routes)
    probe_app.get(path)(handler)
    return probe_app, routes_before


def test_error_response_carries_security_headers():
    """t26 AC-1: a forced 500 carries the contract body AND the security headers.

    The probe route raises a plain ``RuntimeError`` that no route-level handler catches,
    so the answer must come out of the exception-handler layer - which sits inside the
    headers layer - not from a mocked response.
    """

    async def _boom():
        raise RuntimeError("forced failure for t26 AC-1")

    probe_app, routes_before = _add_probe_route("/_probe_boom", _boom)
    try:
        probe_client = TestClient(probe_app, raise_server_exceptions=False)
        resp = probe_client.get("/_probe_boom")
        assert resp.status_code == 500
        # the contract 500 body (t18 / B-10 AC-10 shape)
        body = resp.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"
        assert body["error"]["message"] == "Internal server error"
        # and the four security headers the audit found missing on 500s
        assert resp.headers.get("X-Request-ID")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    finally:
        del probe_app.router.routes[routes_before:]


def test_csp_on_html_responses():
    """t26 AC-2: every HTML response carries a non-empty (report-only) CSP.

    Report-only is the accepted first step, so the test accepts either the
    report-only or the blocking header name, but the directive must be non-empty.
    """
    from fastapi.responses import HTMLResponse

    async def _html():
        return HTMLResponse("<html><body>probe</body></html>")

    probe_app, routes_before = _add_probe_route("/_probe_html", _html)
    try:
        probe_client = TestClient(probe_app, raise_server_exceptions=False)
        resp = probe_client.get("/_probe_html")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        csp = resp.headers.get("Content-Security-Policy-Report-Only") or resp.headers.get(
            "Content-Security-Policy"
        )
        assert csp, "an HTML response must carry a non-empty CSP directive"
        # the gate is content-type based: the JSON /health probe carries no CSP
        health = client.get("/health")
        assert "content-security-policy-report-only" not in health.headers
        assert "content-security-policy" not in health.headers
    finally:
        del probe_app.router.routes[routes_before:]


def test_request_id_bounded():
    """t26 AC-3: the echoed X-Request-ID is at most 128 characters.

    Over-long and empty/whitespace supplied ids are replaced by a server-minted
    UUID4; a valid supplied id (<=128 chars) is still echoed unchanged.
    """
    # 3000-char caller-supplied id: not reflected, replaced by a valid UUID4
    long_id = "a" * 3000
    rid = client.get("/health", headers={"X-Request-ID": long_id}).headers.get("X-Request-ID")
    assert rid != long_id
    assert len(rid) <= 128
    assert uuid.UUID(rid).version == 4
    # 129 chars is already over the bound
    over = "c" * 129
    rid_over = client.get("/health", headers={"X-Request-ID": over}).headers.get("X-Request-ID")
    assert rid_over != over
    assert len(rid_over) <= 128
    # whitespace-only is not a usable id
    rid_blank = client.get(
        "/health", headers={"X-Request-ID": "   "}
    ).headers.get("X-Request-ID")
    assert rid_blank != "   "
    assert len(rid_blank) <= 128
    assert uuid.UUID(rid_blank).version == 4
    # exactly 128 chars is within the bound and is echoed unchanged
    edge = "b" * 128
    assert (
        client.get("/health", headers={"X-Request-ID": edge}).headers.get("X-Request-ID")
        == edge
    )


def test_cache_control_no_store():
    """t26 AC-4: JSON from the API surfaces carries Cache-Control: no-store."""

    async def _api_json():
        return {"ok": True}

    probe_app, routes_before = _add_probe_route("/api/v1/_probe_json", _api_json)
    try:
        probe_client = TestClient(probe_app, raise_server_exceptions=False)
        resp = probe_client.get("/api/v1/_probe_json")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        assert resp.headers.get("Cache-Control") == "no-store"
        # a real staff surface: unauthenticated, it answers a JSON 401 - still no-store
        staff = client.get("/api/v1/staff/tables")
        assert staff.headers["content-type"].startswith("application/json")
        assert staff.headers.get("Cache-Control") == "no-store"
        # /health sits outside /api/v1 and is not subject to the no-store rule
        assert client.get("/health").headers.get("Cache-Control") != "no-store"
    finally:
        del probe_app.router.routes[routes_before:]


def test_hsts_gated(monkeypatch):
    """t26 AC-5: HSTS is emitted only when the config flag is enabled.

    The flag is read per request through ``get_settings()``, so the test flips it
    in-process by patching the environment and clearing the settings cache; both
    directions (absent when disabled, present when enabled) are asserted.
    """
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        # disabled by default: the header is absent
        resp = client.get("/health")
        assert "strict-transport-security" not in resp.headers
        # enabled: the header is emitted
        monkeypatch.setenv("HSTS_ENABLED", "true")
        get_settings.cache_clear()
        resp = client.get("/health")
        hsts = resp.headers.get("Strict-Transport-Security")
        assert hsts, "HSTS_ENABLED must emit the Strict-Transport-Security header"
        assert "max-age=" in hsts
    finally:
        get_settings.cache_clear()
