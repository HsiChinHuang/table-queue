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
