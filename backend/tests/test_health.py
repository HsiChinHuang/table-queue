"""Tests for the health endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


def test_health_returns_status_version_env(client: TestClient):
    """Verify /health endpoint returns correct JSON shape."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert "status" in data
    assert "version" in data
    assert "env" in data

    assert data["status"] == "ok"
    assert isinstance(data["version"], str)
    assert isinstance(data["env"], str)


def test_health_reports_the_environment_the_process_was_given(client: TestClient):
    """T20 AC-3 / D-4: the ``env`` field is the label the process was *given*, not one it inferred.

    Presence was the old assertion, and presence is no longer the interesting fact: audit D-2
    reproduced this endpoint answering ``env=development`` to an unauthenticated caller in a process
    whose operator had never named an environment. Once D-1 makes the setting required there is no
    implicit value left to report, so a test that still only checked the field existed would pass
    unchanged on the broken tree - it would even pass on a tree that hard-coded the answer.

    The comparison is against the settings the process actually resolved rather than against a
    literal, because the suite's own environment statement (``conftest.py``) is what supplies the
    value here, and pinning one literal would make this file refuse a rebind that other modules do
    on purpose. What the test does pin is the two properties D-4 names: the reported value equals
    the resolved one, and that value is on the allow-list rather than an arbitrary string.
    """
    from app.config import ENVIRONMENTS, get_settings

    response = client.get("/health")

    assert response.status_code == 200
    reported = response.json()["env"]
    resolved = get_settings().env
    assert reported == resolved, (
        f"/health reported env={reported!r} while the process resolved env={resolved!r}: the field "
        "is answering from somewhere other than the setting the operator chose"
    )
    assert reported in ENVIRONMENTS, (
        f"/health published env={reported!r}, which is not a name this application recognises"
    )
