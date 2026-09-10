"""FastAPI application with lifespan, health endpoint, and bootstrap."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.database import Base, engine

settings = get_settings()


def bootstrap_defaults(db):
    """Bootstrap default Restaurant, Branch, and Settings if missing.

    Uses raw SQLAlchemy Core/inspection to avoid importing B-02 models.
    This ensures B-02 can replace the models later without breaking this code.

    Args:
        db: Database session.
    """
    from sqlalchemy import func, inspect, select, text

    # Check if tables exist before attempting to insert
    insp = inspect(db.bind)

    # Check if restaurants table exists and has data
    if "restaurants" in insp.get_table_names():
        result = db.execute(select(func.count()).select_from(text("restaurants")))
        count = result.scalar()
        if count == 0:
            db.execute(
                text(
                    "INSERT INTO restaurants (id, name, created_at, updated_at) "
                    "VALUES (1, :name, :now, :now)"
                ),
                {"name": "Sunny Bistro", "now": "2026-01-01 00:00:00"},
            )

    # Check if branches table exists and has data
    if "branches" in insp.get_table_names():
        result = db.execute(select(func.count()).select_from(text("branches")))
        count = result.scalar()
        if count == 0:
            db.execute(
                text(
                    "INSERT INTO branches "
                    "(id, restaurant_id, name, address, phone, timezone, "
                    "business_day_cutoff_hour, open_time, close_time, "
                    "created_at, updated_at) "
                    "VALUES "
                    "(1, 1, :name, :address, :phone, :timezone, 4, '11:00', '21:00', :now, :now)"
                ),
                {
                    "name": "Taipei Xinyi",
                    "address": "No. 123, Example Rd., Xinyi Dist., Taipei City 110, Taiwan",
                    "phone": "02-1234-5678",
                    "timezone": "Asia/Taipei",
                    "now": "2026-01-01 00:00:00",
                },
            )

    # Check if settings table exists and has data
    if "settings" in insp.get_table_names():
        result = db.execute(select(func.count()).select_from(text("settings")))
        count = result.scalar()
        if count == 0:
            db.execute(
                text(
                    "INSERT INTO settings "
                    "(id, branch_id, hold_minutes, avg_seat_minutes, queue_prefix, "
                    "is_waitlist_open, notification_templates, staff_pin_hash, "
                    "created_at, updated_at) "
                    "VALUES "
                    "(1, 1, 10, 15, 'A', true, '{}', null, :now, :now)"
                ),
                {"now": "2026-01-01 00:00:00"},
            )

    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    On startup:
    - Creates all database tables
    - Bootstraps default Restaurant, Branch, and Settings if missing

    On shutdown:
    - No special cleanup needed
    """
    # Startup
    Base.metadata.create_all(bind=engine)

    # Bootstrap defaults
    from sqlalchemy.orm import Session

    db = Session(engine)
    try:
        bootstrap_defaults(db)
    finally:
        db.close()

    yield

    # Shutdown
    pass


# Create FastAPI app
app = FastAPI(
    title="TableQueue API",
    description="Restaurant waitlist manager API",
    version=settings.app_version,
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Health status with status, version, and env.
    """
    return {
        "status": "ok",
        "version": settings.app_version,
        "env": settings.env,
    }
