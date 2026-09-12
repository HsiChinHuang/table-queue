"""Shared fixtures for B-06's public-endpoint tests.

Why a sibling module instead of only ``tests/conftest.py``: AC-15 counts test functions with
``grep -c '^def test_'`` over the two B-06 files and runs pytest on those two files only, so every
helper both files need lives here as an import, not as a fixture each must redeclare. Nothing in
this
module starts with ``test_``, so neither file gains a phantom test through an import.

The database is a per-module file, not the shared ``./test.db`` that ``app.config`` defaults to: the
AC probes delete ``_b06ac.db`` around each run, and two pytest modules that both seed branch 1 into
one file would see each other's rows. ``:memory:`` is not enough either - ``TestClient`` serves the
request on a worker thread, and a plain in-memory database exists only inside the connection that
opened it, so a ``StaticPool`` over a file is what makes one database visible to both the seed
session and the app.

Every seed row spells out the columns the model only defaults in Python (``status``, ``source``,
``created_at``), because the AC probes seed the same way: a row written by a database default would
make a fixture and a probe disagree about what "a WAITING entry" holds.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, datetime

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/tq_b06_pytest.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("STAFF_PIN", "1234")
os.environ.setdefault("ENV", "development")

if os.sep == "/":  # WSL: the Windows drive is not writable by the venv's platform check
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ``app.main`` is imported for its side effect only: it must be loaded after the env bootstrap
# above, and importing it here means a test module that imports this one first still gets a fully
# configured app rather than a half-built module.
from app import database  # noqa: E402  # B-17: the module, so a swapped-in engine is seen here
from app.main import app  # noqa: E402,F401
from app.models import (  # noqa: E402
    Branch,
    Restaurant,
    Settings,
    WaitlistEntry,
    WaitlistSource,
    WaitlistStatus,
)
from app.services import waitlist as service  # noqa: E402

# The AC probes freeze this instant; a test that also freezes it reads the same business date as the
# probe it mirrors (21:00 Taipei with a 04:00 cutoff is still 2026-09-10).
NOW = datetime(2026, 9, 10, 13, 0, tzinfo=UTC)
BUSINESS_DATE = "2026-09-10"


def fresh_session():
    """Return a session on a schema that was just rebuilt from scratch.

    ``drop_all`` before ``create_all`` is what keeps a board test from inheriting the join test's
    rows: shared fixtures would otherwise leak a queue into the next module and change its
    ``waiting_count``.
    """
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)
    from sqlalchemy.orm import Session

    return Session(bind=database.engine)


def seed_branch(db, *, branch_id: int = 1, is_open: bool = True, prefix: str = "A"):
    """Write the minimum a public route needs: one restaurant, one branch, one settings row.

    Returns the branch, whose ``restaurant`` relationship is what ``branch_info`` reads the name
    from - the name lives on the parent row, never on the branch (specs.md section 6).
    """
    # The rows are upserted rather than inserted because a test may seed twice on purpose: to pause
    # a queue it already opened, or to move the cutoff to the instant a business-date test is about
    # to freeze. Both calls describe the same branch, and SQLite answers a second insert of the same
    # primary key with an IntegrityError that surfaces as a 500 rather than as the assertion the
    # test meant to make. A test that wants a *missing* branch leaves this helper alone and gets
    # the empty schema from ``fresh_session``, so nothing here needs to protect that case.
    # The restaurant is written first and the branch attached to it by id rather than by
    # relationship: ``Branch.restaurant`` has no default, so an instance built with only a
    # ``restaurant_id`` leaves ``branch.restaurant`` as ``None`` and the service's
    # ``branch.restaurant.name`` fails long before the payload is assembled.
    if db.get(Restaurant, branch_id) is None:
        db.add(Restaurant(id=branch_id, name="Sunny Bistro"))
    branch = db.get(Branch, branch_id)
    if branch is None:
        branch = Branch(
            id=branch_id,
            restaurant_id=branch_id,
            name="Taipei Xinyi",
            address="No. 1, Section 5, Zhongxiao East Road",
            phone="02-1234-5678",
            timezone="Asia/Taipei",
            business_day_cutoff_hour=4,
            open_time="11:00",
            close_time="21:00",
        )
        db.add(branch)
    settings = db.get(Settings, branch_id)
    if settings is None:
        settings = Settings(
            branch_id=branch_id,
            hold_minutes=10,
            avg_seat_minutes=15,
            queue_prefix=prefix,
            is_waitlist_open=is_open,
            sound_enabled_default=True,
            notification_templates="{}",
            staff_pin_hash=None,
        )
        db.add(settings)
    settings.is_waitlist_open = is_open
    settings.queue_prefix = prefix
    db.commit()
    return branch


def seed_entry(
    db,
    *,
    branch_id: int = 1,
    queue_number: str,
    seq: int,
    status: WaitlistStatus,
    sort_order: int,
    phone: str | None = None,
    business_date: str = BUSINESS_DATE,
    party_size: int = 4,
    prefix: str = "A",
    name: str | None = None,
    **overrides,
):
    """Write one waitlist row and return it.

    ``phone`` defaults to a hyphenated number whose last three digits are the ``seq``, so a test can
    name the credential it expects (``seq=14`` answers to ``014``) without spelling it out, and so
    the mask a test reads back has the shape the contract's examples carry.
    ``created_at`` is the module ``NOW`` unless overridden, which keeps the derived ``status_token``
    reproducible from the stored columns (R-B06-4).
    """
    defaults = {
        "branch_id": branch_id,
        "queue_number": queue_number,
        "full_queue_number": f"{prefix}-{business_date.replace('-', '')}-{seq:03d}",
        "queue_prefix": prefix,
        "seq": seq,
        "business_date": business_date,
        "name": name or f"Guest {queue_number}",
        "phone": phone or f"0900-000-{seq:03d}",
        "party_size": party_size,
        "status": status,
        "sort_order": sort_order,
        "source": WaitlistSource.CUSTOMER,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(overrides)
    entry = WaitlistEntry(**defaults)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def token_for(entry) -> str:
    """Return the derived credential of a stored entry (the only token that exists, R-B06-4)."""
    return service.derive_status_token(entry)


def a_table_id() -> str:
    """Return a random UUID for a nullable reference column, never a bare int.

    ``waitlist_entries.id`` and ``table_id`` are ``UUID`` columns: handing one an ``int`` does not
    fail loudly at the ORM layer, it fails at statement-compile time with ``'int' object has no
    attribute 'hex'``, which reads like a model bug and is a fixture bug.
    """
    return uuid.uuid4()
