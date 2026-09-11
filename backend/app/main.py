"""FastAPI application for TableQueue.

Features added for B‑04:
- Request‑ID middleware (X-Request-ID header, uuid4 generation/echo)
- Security‑header middleware
- CORS configuration from ``settings.cors_origins``
- Rate‑limiting via ``slowapi`` with ``app.state.limiter``
- Global error handlers from ``app.errors``
- ``bootstrap_defaults`` function exported for tests.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import get_settings
from app.database import Base, engine
from app.errors import register_error_handlers
from app.routers import auth as auth_router
from app.routers import staff as staff_router

settings = get_settings()

# ---------------------------------------------------------------------------
# Rate limiter – module‑level so tests can import ``app.main.limiter``.
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# Helper: bootstrap default data if tables exist but are empty.
# ---------------------------------------------------------------------------

def bootstrap_defaults(db: Any) -> None:
    """Insert default restaurant/branch/settings rows when tables are present.

    This mirrors the original implementation but is now a top‑level function so
    ``tests/test_startup.py`` can import it.
    """
    from sqlalchemy import func, inspect, select, text

    insp = inspect(db.bind)

    if "restaurants" in insp.get_table_names():
        result = db.execute(select(func.count()).select_from(text("restaurants")))
        if result.scalar() == 0:
            db.execute(
                text(
                    "INSERT INTO restaurants (id, name, created_at, updated_at) "
                    "VALUES (1, :name, :now, :now)"
                ),
                {"name": "Sunny Bistro", "now": "2026-01-01 00:00:00"},
            )

    if "branches" in insp.get_table_names():
        result = db.execute(select(func.count()).select_from(text("branches")))
        if result.scalar() == 0:
            db.execute(
                text(
                    "INSERT INTO branches (id, restaurant_id, name, address, phone, timezone, "
                    "business_day_cutoff_hour, open_time, close_time, created_at, updated_at) "
                    "VALUES (1, 1, :name, :address, :phone, :timezone, 4, "
                    "'11:00', '21:00', :now, :now)"
                ),
                {
                    "name": "Taipei Xinyi",
                    "address": "No. 123, Example Rd., Xinyi Dist., Taipei City 110, Taiwan",
                    "phone": "02-1234-5678",
                    "timezone": "Asia/Taipei",
                    "now": "2026-01-01 00:00:00",
                },
            )

    if "settings" in insp.get_table_names():
        result = db.execute(select(func.count()).select_from(text("settings")))
        if result.scalar() == 0:
            db.execute(
                text(
                    "INSERT INTO settings (id, branch_id, hold_minutes, avg_seat_minutes, "
                    "queue_prefix, is_waitlist_open, sound_enabled_default, "
                    "notification_templates, staff_pin_hash, created_at, updated_at) "
                    "VALUES (1, 1, 10, 15, 'A', true, true, '{}', null, :now, :now)"
                ),
                {"now": "2026-01-01 00:00:00"},
            )
    db.commit()

# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and bootstrap defaults on startup; no special shutdown."""
    Base.metadata.create_all(bind=engine)
    from sqlalchemy.orm import Session

    db = Session(engine)
    try:
        bootstrap_defaults(db)
    finally:
        db.close()
    yield

# ---------------------------------------------------------------------------
# FastAPI app creation and middleware wiring.
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TableQueue API",
    description="Restaurant waitlist manager API",
    version=settings.app_version,
    lifespan=lifespan,
)

# Store limiter for external access and SlowAPI middleware.
app.state.limiter = limiter

# CORS - allow-list comes from settings.cors_origins (comma separated).
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SlowAPI middleware (must come after CORS).
app.add_middleware(SlowAPIMiddleware)

# Request‑ID and security‑header middleware.
def _add_security_headers(response: Response) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

def _ensure_request_id(request: Request, response: Response) -> None:
    rid = request.headers.get("X-Request-ID")
    if not rid:
        rid = str(uuid.uuid4())
    response.headers["X-Request-ID"] = rid

@app.middleware("http")
async def add_headers(request: Request, call_next: Callable[[Request], Response]):
    response = await call_next(request)
    _ensure_request_id(request, response)
    _add_security_headers(response)
    return response

# Register global error handlers and include the auth router (B-05).
register_error_handlers(app)
auth_router.configure_limiter(limiter)
app.include_router(auth_router.router)
staff_router.configure_limiter(limiter)
app.include_router(staff_router.router)

# ---------------------------------------------------------------------------
# Probe routes for test ACs.
# ---------------------------------------------------------------------------


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint returning status, version and environment."""
    return {"status": "ok", "version": settings.app_version, "env": settings.env}

