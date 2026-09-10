"""Tests for B-02 SQLAlchemy models.

Uses an in-memory SQLite database with a single shared connection so that
relationship loads see the same transaction as the inserts.
"""
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Branch,
    CancelledReason,
    Restaurant,
    Settings,
    Table,
    TableStatus,
    WaitlistEntry,
    WaitlistSource,
    WaitlistStatus,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)
    with test_session() as s:
        yield s
    Base.metadata.drop_all(engine)


def make_branch() -> Branch:
    return Branch(
        restaurant=Restaurant(name="Sunny Bistro"),
        name="Taipei Xinyi",
        address="No. 1, Section 5, Zhongxiao East Road",
        phone="+886-2-0000-0000",
        open_time="11:00",
        close_time="22:00",
    )


def make_table(label: str = "A1", **kwargs) -> Table:
    """Build a Table with sane defaults; kwargs override."""
    defaults: dict = {"label": label, "capacity": 2, "sort_order": 1}
    defaults.update(kwargs)
    return Table(**defaults)


def make_entry(branch: Branch, queue_number: str = "A001", **kwargs) -> WaitlistEntry:
    """Build a WaitlistEntry attached to branch; kwargs override."""
    seq = int(queue_number[-3:])
    defaults: dict = {
        "queue_number": queue_number,
        "full_queue_number": f"A-20260910-{seq:03d}",
        "queue_prefix": "A",
        "seq": seq,
        "business_date": "2026-09-10",
        "name": "Ada",
        "phone": "0912-345-678",
        "party_size": 2,
        "sort_order": 1,
    }
    defaults.update(kwargs)
    return WaitlistEntry(branch=branch, **defaults)


def test_create_all_and_round_trip(session: Session):
    branch = make_branch()
    session.add(branch)
    session.commit()

    loaded = session.query(Branch).one()
    assert loaded.name == "Taipei Xinyi"
    assert loaded.restaurant.name == "Sunny Bistro"
    assert loaded.timezone == "Asia/Taipei"
    assert loaded.business_day_cutoff_hour == 4
    assert loaded.id is not None


def test_table_defaults_and_enum(session: Session):
    branch = make_branch()
    branch.tables = [make_table("A1")]
    session.add(branch)
    session.commit()

    table = session.query(Table).one()
    assert table.status is TableStatus.AVAILABLE
    assert table.is_active is True
    assert table.section is None
    assert isinstance(table.created_at, datetime)


def test_waitlist_defaults_and_enums(session: Session):
    branch = make_branch()
    session.add(make_entry(branch))
    session.commit()

    entry = session.query(WaitlistEntry).one()
    assert entry.status is WaitlistStatus.WAITING
    assert entry.source is WaitlistSource.CUSTOMER
    assert entry.table_id is None
    assert entry.called_at is None


def test_status_transitions_persist(session: Session):
    branch = make_branch()
    table = make_table("B1", capacity=4)
    branch.tables = [table]
    entry = make_entry(branch)
    session.add(entry)
    session.commit()

    entry.status = WaitlistStatus.CALLED
    entry.called_at = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
    entry.table = table
    session.commit()
    session.expire_all()

    reloaded = session.query(WaitlistEntry).one()
    assert reloaded.status is WaitlistStatus.CALLED
    assert reloaded.table.label == "B1"

    reloaded.status = WaitlistStatus.SEATED
    reloaded.seated_at = datetime(2026, 9, 10, 12, 5, tzinfo=UTC)
    session.commit()
    session.expire_all()
    assert session.query(WaitlistEntry).one().status is WaitlistStatus.SEATED


def test_cancelled_reason_optional(session: Session):
    branch = make_branch()
    session.add(
        make_entry(
            branch,
            status=WaitlistStatus.CANCELLED,
            cancelled_reason=CancelledReason.STAFF,
            closed_at=datetime(2026, 9, 10, 13, 0, tzinfo=UTC),
        )
    )
    session.add(make_entry(branch, queue_number="A002", seq=2, sort_order=2))
    session.commit()

    cancelled = session.query(WaitlistEntry).filter_by(queue_number="A001").one()
    plain = session.query(WaitlistEntry).filter_by(queue_number="A002").one()
    assert cancelled.cancelled_reason is CancelledReason.STAFF
    assert plain.cancelled_reason is None


def test_settings_defaults_one_to_one(session: Session):
    branch = make_branch()
    branch.settings = Settings()
    session.add(branch)
    session.commit()

    settings = session.query(Settings).one()
    assert settings.hold_minutes == 10
    assert settings.avg_seat_minutes == 15
    assert settings.queue_prefix == "A"
    assert settings.is_waitlist_open is True
    assert settings.sound_enabled_default is True
    assert settings.notification_templates == "{}"


def test_unique_table_label_per_branch(session: Session):
    branch = make_branch()
    branch.tables = [make_table("A1"), make_table("A1", sort_order=2)]
    session.add(branch)
    with pytest.raises(IntegrityError):
        session.commit()


def test_unique_branch_one_to_one_settings(session: Session):
    branch = make_branch()
    branch.settings = Settings()
    session.add(branch)
    session.commit()

    other = Settings(branch_id=branch.id)
    session.add(other)
    with pytest.raises(IntegrityError):
        session.commit()


def test_cascade_delete_branch_children(session: Session):
    branch = make_branch()
    branch.tables = [make_table("A1")]
    branch.settings = Settings()
    session.add(make_entry(branch, status=WaitlistStatus.SEATED))
    session.commit()

    table_pk = session.query(Table).one().id
    session.delete(session.query(Branch).one())
    session.commit()

    assert session.query(Table).count() == 0
    assert session.query(Settings).count() == 0
    assert session.query(WaitlistEntry).count() == 0
    assert session.query(WaitlistEntry).filter_by(table_id=table_pk).count() == 0
