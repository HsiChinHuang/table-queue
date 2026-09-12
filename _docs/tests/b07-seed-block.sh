# Shared probe-seeder for the B-07 AC blocks, extracted from this file's round-3 text.
# The marked line below is the only line a block keeps from this region: it is the heredoc
# wrapper that receives the payload appended after the comments, so scratch seed.py lands
# as valid python. The payload starts on the next line and is the byte-for-byte text every
# AC block carried inline before this extraction (R-B07-7); nothing is dropped and nothing
# here is ever executed by a block, so the marker line costs an AC nothing. The end-marker
# line at the very bottom is only the closing token of the heredoc shown here.
# B07_SEED_WRAPPER sed "$W/seed.py" <<'SEEDEOF'

# Probe seeder for the B-07 AC blocks: inlined verbatim so the block is
# self-contained in any checkout. See the docstring for the three SQLite
# traps it exists to step around.
"""Seeding helpers for the B-07 PM probes (scratch tooling, never committed).

Every AC block writes this exact file into its own scratch directory beside its own probe, so
this copy on disk and the copies inside the issue file have to stay identical. Nothing from
``backend/app`` is used here except what an AC exists to measure.

Three traps this helper exists to step around, all measured on this tree with the project
venv (SQLAlchemy 2.0.52, stock CPython 3.12 ``sqlite3``):

1. ``app.models`` spells every primary and foreign uuid key as ``sqlalchemy.UUID``, whose
   native bind processor is a no-op, so what reaches SQLite is whatever the DBAPI decides about
   the object it was handed. A ``uuid.UUID`` binds as a REAL (``select typeof(id) from tables``
   answers ``real`` and the value reads back as ``4.0008001e+19``), and the next SELECT over
   that column dies inside ``uuid.UUID(value)`` with ``AttributeError: 'float' object has no
   attribute 'replace'``. A plain ``str`` is refused on the write with ``AttributeError: 'str'
   object has no attribute 'hex'``. Both shapes fail, so from this interpreter no uuid can be
   written through the shipped column type at all: :func:`swap_uuid_type` rebinds the name
   before ``app.models`` is first imported.
2. The venv ships ``_editable_impl_table_queue_backend.pth``, which puts the *long-lived
   checkout's* ``backend`` directory on ``sys.path`` at interpreter start. A probe that only
   prepends its own ``backend`` can therefore import ``app.*`` from a different worktree than
   the one being graded, and the file it reports on is not the file the AC is about. So
   :func:`boot` prepends the repo under test and then asserts where ``app.config`` came from.
3. Timestamps: ``DateTime(timezone=True)`` round-trips without an offset on SQLite, so every
   instant this file hands out is aware UTC and every comparison a probe makes reattaches UTC
   first.

The one deliberate exception to "scratch tooling" is :func:`fake_staff_router`: the mounted app
grew no staff surface on ``main``, so a block that has to measure the transport before a route
exists measures it on a route the seeder mounts through the real ``app.dependencies.Staff``
dependency. Every statement such a block prints is labelled with the file it came from, and
AC-14 is written so it cannot go green on the fake.
"""

import os
import sys
import warnings
from datetime import UTC, datetime, timedelta
from uuid import UUID as _pyUUID

import sqlalchemy as sa
from sqlalchemy import String

# The repo under test is the working directory this probe was started from. The project venv
# ships ``_editable_impl_table_queue_backend.pth``, whose single line is the long-lived
# checkout's ``backend`` path, so that tree is already on ``sys.path`` when the interpreter
# starts; ``_strip_editable_path`` below removes it and ``boot`` asserts the import really came
# from the tree being graded.
REPO = os.environ.get("B07_REPO") or os.getcwd()
BACKEND_UNDER_TEST = os.path.join(REPO, "backend")


def _strip_editable_path():
    """Drop every ``sys.path`` entry that is another checkout's ``backend`` directory."""
    want = os.path.realpath(BACKEND_UNDER_TEST)
    keep = [entry for entry in sys.path
            if not (entry and os.path.isdir(entry)
                    and entry.rstrip(os.sep).endswith("backend")
                    and os.path.realpath(entry) != want
                    and os.path.isfile(os.path.join(entry, "app", "models.py")))]
    if len(keep) != len(sys.path):
        sys.path[:] = keep


def _purge_app_modules():
    """Drop every already-imported ``app.*`` module from ``sys.modules``.

    A probe that imports ``app.models`` on the line above ``seed.boot()`` has already bound the
    long-lived checkout's mappers, and the origin assertion would then be true of a tree nobody
    is grading. Dropping the cached modules and re-importing is what makes the assertion a
    statement about the tree under test rather than about import order in the probe.
    """
    for name in [key for key in list(sys.modules)
                 if key == "app" or key.startswith("app.") or key in ("seed", "probe")]:
        del sys.modules[name]



class TextUUID(String):
    """A uuid stored as text, which is what ``sqlalchemy.UUID`` has to mean for a probe.

    A ``String`` subclass whose ``load_dialect_impl`` answers itself, so no dialect gets to
    swap its native ``UUID`` back in. ``cache_ok`` because one instance is shared across the
    whole schema. The bind side accepts ``str`` or ``uuid.UUID`` and writes 32-character hex;
    the result side parses it back to ``uuid.UUID``, which is the round trip the shipped type
    documents and this driver will not give.
    """

    __visit_name__ = "CHAR"
    cache_ok = True

    def __init__(self, *args, **kwargs):
        """Absorb the keyword arguments the shipped column is spelled with."""
        kwargs.pop("native_uuid", None)
        kwargs.pop("as_uuid", None)
        kwargs.setdefault("length", 32)
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(self)

    def bind_processor(self, dialect):
        def bind(value):
            if value is None:
                return None
            return value.hex if isinstance(value, _pyUUID) else str(value).replace("-", "")

        return bind

    def result_processor(self, dialect, coltype):
        def result(value):
            if value is None or isinstance(value, _pyUUID):
                return value
            text = str(value)
            if "-" in text:
                return _pyUUID(text)
            return _pyUUID(text[:8] + "-" + text[8:12] + "-" + text[12:16]
                           + "-" + text[16:20] + "-" + text[20:])

        return result


def swap_uuid_type():
    """Make ``sqlalchemy.UUID`` mean :class:`TextUUID` before ``app.models`` is imported.

    ``models.py`` evaluates ``UUID(as_uuid=True)`` at class-definition time, so the only hook
    that reaches it is the module attribute, rebound before the first ``import app.models``. An
    engine-level ``type_encoders`` entry cannot do this: ``URL.get_dialect`` builds the dialect
    from scratch and copies only ``connect_args`` and ``execution_options``, so an encoder
    handed to ``create_engine`` never reaches the first statement.
    """
    sa.UUID = TextUUID
    import sqlalchemy.sql.sqltypes as sqltypes

    sqltypes.UUID = TextUUID


DAY = "2026-09-10"
NOW = datetime(2026, 9, 10, 13, 0, tzinfo=UTC)
"""The 13:00Z anchor the contract examples use: 21:00 Taipei with cutoff 4 is 2026-09-10.

This is the ANCHOR the contract's prose and `business_date` are written against, not the instant a
probe measures. The product decides hold expiry against its own clock (`app.dependencies.get_now`,
a wall clock), so a seed that wrote `called_at` against this anchor while the product read the real
wall clock was already two days stale the moment any probe ran: measured at 2026-09-12, a row the
block meant to be "called 1 minute ago, still inside its hold" sat 2,879 minutes past that hold, and
every status assertion downstream inverted. The anchor stays for the day it names; `at` does not use
it. See `at` below.
"""


def at(minutes):
    """Return the live clock plus whole minutes, as an aware UTC datetime.

    Deliberately NOT anchored to `NOW` above. The product reads `app.dependencies.get_now`, a wall
    clock, so a hold-relative `called_at` has to be relative to the same now the product reads:
    `at(-30)` means 30 minutes before the product's now, and a `hold=10` row is expired for the
    product exactly when the block says it is. Anchoring to a fixed example date made the probe's
    verdict depend on the day it ran, which is an instrumentation bug, not a product behaviour -
    measured: with the anchor, every seeded CALLED row read as long-expired and AC-3's unexpired
    control row was reported NO_SHOW. `business_date` still comes from `NOW`'s day, because that is
    the day the contract's examples are written about.
    """
    return datetime.now(UTC) + timedelta(minutes=minutes)


def boot():
    """Return (SessionLocal, app) on a freshly dropped and recreated schema.

    Raises ``RuntimeError`` if the imported ``app`` package does not live under the working
    directory's own ``backend``, which is the guard against the venv's editable-install
    ``.pth`` entry: a probe that measured another checkout's code would print a verdict about a
    tree nobody is grading.
    """
    swap_uuid_type()
    _strip_editable_path()
    _purge_app_modules()
    sys.path.insert(0, BACKEND_UNDER_TEST)
    import app.config  # noqa: F401  first, so the origin check precedes every other app import

    came_from = os.path.realpath(os.path.dirname(os.path.dirname(app.config.__file__)))
    if came_from != os.path.realpath(BACKEND_UNDER_TEST):
        msg = "app came from " + came_from + " instead of " + os.path.realpath(BACKEND_UNDER_TEST)
        raise RuntimeError(msg)
    import app.models  # noqa: F401  registers the mappers before create_all
    from app.database import Base, SessionLocal, engine
    from app.main import app

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return SessionLocal, app


def raw(n):
    """Return the n-th seeded table primary key, as text."""
    return "00000000-0000-4000-800%d-000000000001" % n


TABLE_A1 = raw(1)
TABLE_B1 = raw(2)
TABLE_C1 = raw(3)
"""A1 and B1 start AVAILABLE; C1 starts OCCUPIED, so a seat that must refuse has a real row."""


def seed(session_factory):
    """Write one restaurant, one branch, one settings row and three tables; return the session."""
    from app.models import Branch, Restaurant, Settings, Table
    from app.models import TableStatus as TS

    db = session_factory()
    db.add(Restaurant(id=1, name="Sunny Bistro"))
    db.add(Branch(
        id=1, restaurant_id=1, name="Taipei Xinyi", address="a", phone="02-1234-5678",
        timezone="Asia/Taipei", business_day_cutoff_hour=4, open_time="11:00", close_time="21:00",
    ))
    db.add(Settings(
        branch_id=1, hold_minutes=10, avg_seat_minutes=15, queue_prefix="A",
        is_waitlist_open=True, sound_enabled_default=True, notification_templates="{}",
        staff_pin_hash=None,
    ))
    for i, (label, cap, status) in enumerate(
        [("A1", 2, TS.AVAILABLE), ("B1", 4, TS.AVAILABLE), ("C1", 6, TS.OCCUPIED)], start=1
    ):
        db.add(Table(id=raw(i), branch_id=1, label=label, capacity=cap, section="Main Hall",
                     sort_order=i, status=status))
    db.commit()
    return db


def entry(db, *, qn, seq, sort, status="WAITING", phone=None, name=None, party=2, note=None,
          table=None, called_at=None, hold=None, seated_at=None, closed_at=None,
          cancelled_reason=None, created=None):
    """Add one waitlist row with every column spelled out; return the row.

    `phone` defaults to the queue number's OWN sequence tail (`A002` -> `0900-000-002`), so an
    omitted phone still gives the row a three-digit tail a `search` probe can name. A block that
    needs a different tail passes `phone` explicitly - AC-5's three rows name `0900-000-901/-902/-903`
    for exactly that reason - and a block that reads the tail back out of a `queue_number` would be
    reading a number the seeder never wrote.
    """
    from app.models import CancelledReason, WaitlistEntry, WaitlistSource, WaitlistStatus

    row = WaitlistEntry(
        branch_id=1, queue_number=qn, full_queue_number="A-20260910-%03d" % seq,
        queue_prefix="A", seq=seq, business_date=DAY,
        name=name or ("Guest " + qn), phone=phone or ("0900-000-%03d" % seq),
        party_size=party, note=note, status=WaitlistStatus[status], sort_order=sort,
        source=WaitlistSource.CUSTOMER, hold_minutes_snapshot=hold, table_id=table,
        called_at=called_at, seated_at=seated_at, closed_at=closed_at,
        cancelled_reason=CancelledReason[cancelled_reason] if cancelled_reason else None,
        created_at=created or NOW, updated_at=created or NOW,
    )
    db.add(row)
    db.commit()
    return row


def ids(db):
    """Return {queue_number: entry uuid} for the rows this probe seeded."""
    from app.models import WaitlistEntry

    return {row.queue_number: str(row.id)
            for row in db.query(WaitlistEntry).order_by(WaitlistEntry.sort_order).all()}


def tables(db, label=None):
    """Return {label: status value} for the seeded tables, optionally one label only."""
    from app.models import Table

    query = db.query(Table)
    if label is not None:
        query = query.filter(Table.label == label)
    return {row.label: row.status.value for row in query.all()}


def row(db, qn):
    """Return the entry seeded under this queue number, expired from the identity map."""
    from app.models import WaitlistEntry

    db.expire_all()
    return db.query(WaitlistEntry).filter(WaitlistEntry.queue_number == qn).first()


def models():
    """Return the ``app.models`` module of the tree under test (import it after :func:`boot`)."""
    import app.models

    return app.models


def mount_probe(router):
    """Mount ``router`` on the app under test and return it (call after :func:`boot`)."""
    from app.main import app

    app.include_router(router)
    return app


def transport_probe(router, client_headers):
    """Return (status_code, body) for a probe request through ``router``'s first route.

    Kept separate so a block can call it twice - once with the staff header and once without -
    without every block re-implementing the client.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    route = list(router.routes)[0]
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(route.path.format(entry_id="00000000-0000-4000-8001-000000000001"),
                      headers=client_headers, json={})
    return resp.status_code, resp.text


def fake_staff_router(actions):
    """Return a throwaway ``APIRouter`` whose routes take the real ``Staff`` dependency.

    ``actions`` maps an action suffix to the status it should require. Each route calls
    :func:`transport`, which *is* the merged code under measurement: the section 11 envelope from
    ``app.errors.AppError`` and the 1-20 body bound by ``app.schemas.SeatWaitlistRequest``. The
    route paths are namespaced under ``/api/v1/_b07probe`` so that a probe using this can never be
    mistaken for the contract surface, and AC-14's block reads the live
    ``/api/v1/staff/waitlist`` path, where no fake can be mounted.
    """
    from fastapi import APIRouter, Body, Depends

    from app.dependencies import Staff
    from app.errors import AppError

    router = APIRouter(prefix="/api/v1/_b07probe")

    def transport(entry_status, code, body):
        """Raise the way the merged error layer raises, after the body model has been bound.

        ``AppError`` takes ``message`` as a keyword and derives the HTTP status from
        ``ERROR_CODES``, so an illegal transition here lands as the same 409 envelope a real
        endpoint produces.
        """
        if entry_status not in actions:
            raise AppError(code, message=code + ": entry is " + str(entry_status))
        return {"echo": body.model_dump(mode="json") if body is not None else None}

    for suffix, required in actions.items():
        def make(required=required, suffix=suffix):
            @router.post("/waitlist/{entry_id}/" + suffix)
            def endpoint(user: Staff, entry_id: str,
                         body: dict | None = Body(default=None)):
                payload = body or {}
                if suffix == "seat":
                    from app.schemas import SeatWaitlistRequest

                    bound = SeatWaitlistRequest.model_validate(payload)
                    return transport(required, "WAITLIST_INVALID_STATUS", bound)
                return transport(required, "WAITLIST_INVALID_STATUS", None)

            return endpoint

        make()
    return router


def login(client):
    """Return the Authorization header a real login hands back (B-05 is merged)."""
    import time

    from jose import jwt

    now = int(time.time())
    token = jwt.encode({"sub": "staff", "role": "staff", "iat": now, "exp": now + 3600},
                       os.environ["JWT_SECRET"], algorithm="HS256")
    return {"Authorization": "Bearer " + token}
SEEDEOF
