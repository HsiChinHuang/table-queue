"""Tests for configuration validation (B-01 AC-12: fail fast on missing env)."""
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

_CHILD = """
import os
for key in ["DATABASE_URL", "JWT_SECRET", "STAFF_PIN"]:
    os.environ.pop(key, None)
from app.config import Settings
try:
    Settings(_env_file=None)
    print("NO_ERROR")
except Exception:
    print("VALIDATION_ERROR")
"""


def test_config_validates_required_env():
    """Settings must raise when required env vars are missing.

    Runs in a subprocess with a cleaned environment and _env_file=None so a
    local .env file can never mask the failure.
    """
    result = subprocess.run(
        [sys.executable, "-c", _CHILD],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
    )
    assert "VALIDATION_ERROR" in result.stdout, (
        "Settings must fail fast when required env vars are missing; got: "
        + result.stdout
        + result.stderr
    )
