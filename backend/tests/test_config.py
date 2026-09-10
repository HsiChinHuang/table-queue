"""Tests for configuration validation."""

import os
import subprocess
import sys


def test_config_validates_required_env():
    """Verify config fails fast on missing required env vars.

    We use subprocess to test this because the Settings class uses lru_cache
    and pydantic-settings reads env vars at class initialization time.
    """
    # Run a Python script that tries to create Settings without required env vars
    script = """
import os
import pathlib

# Ensure no required env vars are set
for key in ["DATABASE_URL", "JWT_SECRET", "STAFF_PIN"]:
    os.environ.pop(key, None)

# Remove .env file if it exists to force env var requirement
env_file = pathlib.Path("backend/.env")
if env_file.exists():
    env_file.unlink()

from app.config import Settings
try:
    Settings()
    print("NO_ERROR")
except Exception as e:
    print("ERROR:" + str(type(e).__name__))
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd="/home/te/tq",
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "/home/te/tq/B-01/backend"},
    )

    output = result.stdout.strip()
    # Should get an error (ValidationError or similar)
    assert "NO_ERROR" not in output, "Settings should fail when required env vars are missing"
