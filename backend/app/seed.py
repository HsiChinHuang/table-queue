# ruff: noqa
"""Seed script for TableQueue backend.

Runs as ``python -m app.seed``. Creates initial data fixtures.
"""
import argparse
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo

import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models import (
    Restaurant,
    Branch,
    Settings as SettingsModel,
    Table,
    WaitlistEntry,
    TableStatus,
    WaitlistStatus,
    WaitlistSource,
    CancelledReason,
)
from app.database import Base


def get_engine():
    """Create SQLAlchemy engine from current environment settings."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=settings.env == "development",
    )


def get_session(engine):
    """Return a new SQLAlchemy session bound to the provided engine."""
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return session_factory()


def create_schema(engine) -> None:
    Base.metadata.create_all(engine)


def drop_schema(engine) -> None:
    Base.metadata.drop_all(engine)


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def seed_data(reset: bool = False) -> int:
    engine = get_engine()
    # Ensure schema exists before checking data.
    create_schema(engine)
    try:
        with get_session(engine) as session:
            has_data = (
                session.query(Restaurant).first()
                or session.query(Branch).first()
                or session.query(SettingsModel).first()
            )
    except Exception:
        has_data = False
    if has_data and not reset:
        print("seed: data already present – skipping (already exists)")
        return 0
    if reset:
        drop_schema(engine)
        print("seed: schema dropped – resetting")
        create_schema(engine)
    # Seed data.
    with get_session(engine) as session:
        restaurant = Restaurant(name="Sunny Bistro")
        session.add(restaurant)
        session.flush()
        branch = Branch(
            restaurant_id=restaurant.id,
            name="Taipei Xinyi",
            address="No. 123, Example Rd., Xinyi Dist., Taipei City 110, Taiwan",
            phone="02-1234-5678",
            timezone="Asia/Taipei",
            business_day_cutoff_hour=4,
            open_time="11:00",
            close_time="21:00",
        )
        session.add(branch)
        session.flush()
        pin_hash = hash_pin("1234")
        settings = SettingsModel(
            branch_id=branch.id,
            hold_minutes=10,
            avg_seat_minutes=15,
            queue_prefix="A",
            is_waitlist_open=True,
            sound_enabled_default=True,
            notification_templates="{}",
            staff_pin_hash=pin_hash,
        )
        session.add(settings)
        session.flush()
        # Tables
        table_defs = []
        for i in range(1, 5):
            table_defs.append((f"A{i}", 2))
        for i in range(1, 5):
            table_defs.append((f"B{i}", 4))
        for i in range(1, 3):
            table_defs.append((f"C{i}", 6))
        tables = []
        for idx, (label, cap) in enumerate(table_defs, start=1):
            tbl = Table(
                branch_id=branch.id,
                label=label,
                capacity=cap,
                section=label[0],
                sort_order=idx,
                status=TableStatus.AVAILABLE,
                is_active=True,
            )
            tables.append(tbl)
            session.add(tbl)
        session.flush()
        b1 = next(t for t in tables if t.label == "B1")
        b1.status = TableStatus.OCCUPIED
        # Business date
        now_taipei = datetime.now(ZoneInfo("Asia/Taipei"))
        business_date = (now_taipei - timedelta(hours=4)).date().isoformat()
        phones = [f"0900-000-00{i}" for i in range(1, 10)]
        names = ["Alice", "Bob", "Carol", "David", "Erin", "Frank", "Grace", "Henry", "Iris"]
        notes = [
            "window seat",
            "high chair needed",
            "birthday dinner",
            "quiet area",
            "near exit",
            None,
            None,
            None,
            None,
        ]
        party_sizes = [2, 4, 6, 2, 4, 6, 2, 4, 6]
        status_mix = [
            WaitlistStatus.WAITING,
            WaitlistStatus.WAITING,
            WaitlistStatus.WAITING,
            WaitlistStatus.WAITING,
            WaitlistStatus.WAITING,
            WaitlistStatus.CALLED,
            WaitlistStatus.SEATED,
            WaitlistStatus.NO_SHOW,
            WaitlistStatus.CANCELLED,
        ]
        for seq in range(1, 10):
            status = status_mix[seq - 1]
            entry = WaitlistEntry(
                branch_id=branch.id,
                queue_number=f"A{seq:03d}",
                full_queue_number=f"A-{business_date.replace('-', '')}-{seq:03d}",
                queue_prefix="A",
                seq=seq,
                business_date=business_date,
                name=names[seq - 1],
                phone=phones[seq - 1],
                party_size=party_sizes[seq - 1],
                note=notes[seq - 1],
                status=status,
                sort_order=seq,
                source=WaitlistSource.CUSTOMER,
                hold_minutes_snapshot=10,
            )
            if status == WaitlistStatus.CALLED:
                entry.called_at = datetime.now(UTC) - timedelta(minutes=3)
            if status == WaitlistStatus.SEATED:
                entry.seated_at = datetime.now(UTC) - timedelta(minutes=10)
                entry.table_id = b1.id
            if status == WaitlistStatus.NO_SHOW:
                entry.closed_at = datetime.now(UTC) - timedelta(minutes=5)
            if status == WaitlistStatus.CANCELLED:
                entry.closed_at = datetime.now(UTC) - timedelta(minutes=5)
                entry.cancelled_reason = CancelledReason.CUSTOMER
            session.add(entry)
        session.commit()
    print("seed: created 1 restaurant, 1 branch, 1 settings, 10 tables, 9 waitlist entries")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the database with initial data.")
    parser.add_argument("--reset", action="store_true", help="Drop existing data and reseed.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return seed_data(reset=args.reset)

if __name__ == "__main__":
    raise SystemExit(main())
