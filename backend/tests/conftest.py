"""Test environment defaults.

The app fails fast when required env vars are missing (B-01 AC-12), so tests
must provide a complete environment before app modules are imported.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("STAFF_PIN", "1234")
os.environ.setdefault("ENV", "development")
