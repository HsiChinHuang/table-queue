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
