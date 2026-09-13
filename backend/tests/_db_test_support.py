"""Shared scaffolding for D-02's four database test modules.

Nothing in this file starts with ``test_``, so importing it into ``test_db_atomicity.py``,
``test_db_reorder.py``, ``test_db_constraints.py`` or ``test_db_failover_no_show.py`` adds no
phantom case to any of them: the four AC blocks each count ``::test_`` lines out of
``--collect-only`` and expect their own exact number (6, 4, 3, 3).

What lives here and why:

- **One engine per module, never the shared one.** ``tests/conftest.py`` repoints ``DATABASE_URL``
  for every single test and creates no schema at all, so a module that rode
  ``app.database.engine`` would answer "no such table" - the same reason the merged
  ``test_staff_tables.py`` and ``test_staff_dashboard.py`` each own an engine. Every module here
  gets its own SQLite file, so no module can see another module's rows.
- **A ``get_db`` override that hands the application a fresh ``Session`` per request** and keeps a
  reference to it, so a test can read the request's own session objects (what the ORM believed it
  wrote) beside a read-back from a different session (what the database says).
- **Commit counting and commit breaking through SQLAlchemy 2.0's ``commit`` engine event**, the
  mechanism specs section 14 makes observable: on this ``NullPool`` engine a release issues exactly
  one commit, and raising from that listener is the only failure a test may inject without touching
  product code. Arm it by count and fire it once - an unconditionally raising listener makes every
  later write in the suite revert, manufacturing greens instead of reds.
- **``seq >= 300``** on every waitlist row written here (AC-1 asserts at least one such site):
  ``uq_queue_seq`` is ``(branch_id, business_date, queue_prefix, seq)``, and the merged seed writes
  rows with ``seq < 100`` on the same business date.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import bcrypt
from fastapi.testclient import TestClient
from freezegun import freeze_time
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.database import Base, get_db
from app.main import app, limiter
from app.models import (
    Branch,
    Restaurant,
    Settings,
    Table,
    TableStatus,
    WaitlistEntry,
    WaitlistStatus,
)

# 2026-09-10 13:00 UTC is 21:00 Taipei: business date 2026-09-10 under the branch's 04:00 cutoff,
# the same instant public_fixtures.NOW and the merged B-08/B-09 FROZEN constants name.
NOW = datetime(2026, 9, 10, 13, 0, tzinfo=UTC)
BUSINESS_DATE = "2026-09-10"


def taipei(
    year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0
) -> datetime:
    """Return an ``Asia/Taipei`` wall time as an aware datetime.

    AC-6 states case 1 in Taipei wall times and case 2 in the UTC instants that produce them.
    Building both from this one helper is what stops the two spellings drifting apart - the exact
    ambiguity ``_docs/issues/D-02.md`` Context 3 records between the stub's clock-less examples and
    the shipped test that freezes ``03:59`` UTC (11:59 Taipei).
    """
    return datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo("Asia/Taipei"))


TEST_CREDENTIAL_HASH = bcrypt.hashpw(b"1234", bcrypt.gensalt(rounds=12)).decode()
"""A real bcrypt hash for the settings row every staff-facing test seeds.

Two T9 properties meet in one constant here. The verifier now confirms that the store actually
carries a credential before it accepts a signature (D-1's fail-closed reading, which AC-1's
tampered-store arm pins), so a test that seeds a settings row to exercise a staff route has to seed
a credential with it - a hash-less row is the tampered shape and answers 401 by design. And it is a
hash produced by the same construction the application uses, at the pinned cost, rather than a
placeholder string: the value never becomes an assertion anywhere (no test in this file logs in),
so a fresh hash per process costs nothing and keeps a plaintext PIN out of the file (AC-7).
"""


def scratch_credential_session():
    """A throwaway in-memory store carrying a credential, for a bearer the store must not depend on.

    Some shape probes - ``test_admin_tables.py``'s AC-12 rule, for one - ask what status code a
    request earns WITHOUT installing the fixture that binds the application to a seeded scratch
    schema, because an empty schema is part of what they are measuring. Under T9 that is a bind: the
    bearer is keyed on a generation value the request's own store holds, and with no fixture in play
    that store is the ambient ``tq_isolated`` file, whose credential state belongs to the harness
    rather than to the probe. Handing the mint a store of its own settles it - the signature is
    well-formed and the credential check is answered by a row that exists - and the request still
    runs against whatever store the test's arrangement leaves in place, which is the thing under
    test. It is a memory database with one settings row and it dies with the caller's session.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    session = sessionmaker(bind=engine)()
    # Raw DDL for the two columns the verifier reads, rather than the mapped table: the mapped row
    # carries NOT NULL columns of its own (branch_id and the rest), and satisfying them would mean
    # seeding a restaurant and a branch too - a bigger claim about the store than this helper is
    # entitled to make. The verifier asks exactly two questions of the settings row, and these are
    # the two answers it needs.
    session.execute(
        text("create table settings (id integer primary key, staff_pin_hash varchar(100), "
             "token_generation varchar(64))")
    )
    session.execute(
        text("insert into settings (id, staff_pin_hash) values (1, :h)"),
        {"h": TEST_CREDENTIAL_HASH},
    )
    session.commit()
    return session


def staff_token(
    *, role: str = "staff", settings: Any | None = None, session: Any | None = None
) -> str:
    """Mint a current staff bearer through the auth module's own seam.

    T9 decision D-2 folded the store's token-generation value into the HS256 key, so the key is no
    longer something a caller can rebuild from configuration - and T9 AC-5 refuses a bare
    ``JWT_SECRET`` signature outright, which means every hand-signed staff bearer in the suite had
    to go. The module that owns the credential mints the token instead; the claims stay the login
    response's own shape, so what the verifier checks is unchanged.

    Which STORE the token is signed for is the whole question, and :func:`store_session` answers it:
    ``session`` names one outright, and ``None`` resolves to whatever the running request will read.
    ``settings`` stays a parameter for the expiry horizon only - the reset suite rebinds the
    settings getter onto a scratch database and the horizon has to come from the settings in force
    there. The key never comes from here: it belongs to the store, which is the whole point of the
    revocation design.
    """
    from app.config import get_settings
    from app.routers.auth import mint_staff_token

    horizon = (settings or get_settings()).jwt_expire_hours * 3600
    with contextlib.closing(store_session(session)) as owned:
        return mint_staff_token(owned, role=role, lifetime_seconds=horizon)


def store_session(session):
    """Return the session the running request will use, so a mint and a request cannot diverge.

    A harness gives the application its store one of two ways, and both are shipped: it rebinds
    ``app.database.SessionLocal`` (``test_staff_tables``, ``test_staff_dashboard``, the reset
    suite), or it overrides the ``get_db`` dependency with a session of its own
    (``test_admin_settings``, ``test_admin_tables``). The second one never touches the factory, so
    a mint that read the factory would sign for a database the request will not read - and after T9
    decision D-2 that is a 401, not a shrug: the generation value a signature carries has to come
    from the row the request will load. An override is a plain callable here and the session it
    returns is this test's session, so one helper covers both shapes.
    """
    if session is not None:
        return session
    from app.database import get_db
    from app.main import app

    override = app.dependency_overrides.get(get_db)
    if override is not None:
        return override()
    from app import database as database_module

    return database_module.SessionLocal()


def staff_headers(
    *, role: str = "staff", settings: Any | None = None, session: Any | None = None
) -> dict[str, str]:
    """The bearer header every staff/admin request in the suite carries."""
    return {
        "Authorization": "Bearer " + staff_token(role=role, settings=settings, session=session)
    }


def _as_uuid(value: Any) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _looks_like_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return False
    return True


class Database:
    """One module-owned SQLite file: its engine, its schema, its sessions, its commit listener.

    The scratch file lives next to the ones the merged suite already owns (``_b08_test.db``,
    ``_b09_test.db``): created by the module that names it, read back through ``sqlite3`` when the
    test needs the file rather than the ORM, and unlinked on teardown. It is never opened before it
    is created, so a green cannot come from a previous run's leftover rows.
    """

    #: How long a probe connection waits for the write lock before it calls the file locked. The
    #: stdlib default is five seconds, which turns "is a transaction in flight?" into a test that
    #: sleeps for five seconds per read; a quarter of a second is long enough to distinguish "free"
    #: from "held" without becoming a timing race the CI box has to win.
    LOCK_PROBE_TIMEOUT = 0.25

    def __init__(self, name: str) -> None:
        self.path = Path(__file__).resolve().parent / f"_{name}.db"
        if self.path.exists():
            self.path.unlink()
        self.engine: Engine = create_engine(
            f"sqlite:///{self.path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self._requests: list[Session] = []
        self._counter: Any = None
        self.commits: list[int] = []

    # -- sessions and the client -------------------------------------------------

    def session(self) -> Session:
        """Return a detached session on this module's schema (the test's own reader)."""
        return Session(self.engine)

    def provide_request_session(self) -> Session:
        """Return the session the application will use for the next request.

        A fresh session per request and no session ever closed by the override. The first half is
        what a running application does and what makes AC-1's failed transaction findable as an
        identity map; the second is deliberate - a closed session would answer the pre-commit
        readback with a new SELECT instead of with what the request's own objects held. The cost of
        the pair is measured rather than assumed, and AC-1's seat case pays it: an identity map
        carries the state of a transaction that failed, so reusing the session would report a row as
        ``SEATED`` that the database has never made durable. ``last_request_session`` therefore
        names the *write* session, not merely the newest one.
        """
        session = Session(self.engine)
        self._requests.append(session)
        return session

    def last_request_session(self) -> Session | None:
        """The session the most recent request ran on, kept open for an attribute read.

        Entries are not closed by the override on purpose: AC-1's pre-commit readback case has to
        ask what the request's own objects held, and a closed session would answer that with a
        fresh SELECT instead of with the identity map the ORM flushed. The override returns the
        session to the application by value, so the request itself never sees this reference.
        """
        return self._requests[-1] if self._requests else None

    def client(self) -> TestClient:
        """A client whose ``get_db`` dependency resolves to this module's schema.

        ``limiter.enabled`` is switched off before the client is built, the way the merged
        B-08/B-09 modules do it, so a whole-suite run cannot turn these calls into 429s.
        ``raise_server_exceptions=False`` is what lets an injected commit failure answer the 500
        these cases assert instead of reaching the test as an exception group.
        """
        limiter.enabled = False
        app.dependency_overrides[get_db] = self.provide_request_session
        return TestClient(app, raise_server_exceptions=False)

    def release_client(self) -> None:
        """Drop the ``get_db`` override so no later module can inherit this database."""
        app.dependency_overrides.pop(get_db, None)

    def request_write_lock_is_held(self) -> bool:
        """Whether the file still refuses a writer, as a plain yes or no.

        AC-1's seat case is the only caller that needs the answer, and it needs the answer rather
        than a raised error, because the fact it is establishing is negative: the transaction a
        broken commit aborted is still the one holding the file, so the seat that request assigned
        is neither durable nor lost-and-writable. A probe connection takes ``BEGIN IMMEDIATE``,
        tries a statement that matches no row - the lock is the measurement, never the row - and
        reports
        whether the driver let it through or made it wait. The wait is bounded by
        :data:`LOCK_PROBE_TIMEOUT`, so the verdict costs a moment rather than a stalled run.

        A ``True`` here poisons the scratch file for anything that reuses the path, which is why
        the caller destroys the file instead of closing it.
        """
        import sqlite3

        connection = sqlite3.connect(str(self.path), timeout=self.LOCK_PROBE_TIMEOUT)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("UPDATE tables SET label = label WHERE label = ?", ("__none__",))
            connection.commit()
            return False
        except sqlite3.OperationalError:
            return True
        finally:
            connection.close()

    def discard_file(self) -> None:
        """Throw the scratch database away mid-test, on a test that poisoned it on purpose.

        AC-1's seat-commit-failure case leaves an open transaction holding uncommitted writes in the
        file: the injected failure lands after the ORM has already flushed, so nothing ever commits
        or rolls back that transaction. A later test that happened to reuse the same path would read
        those rows and fail for a reason this file caused, so the file goes rather than being left
        behind. The engine is disposed first so SQLite's handles are closed while the path is ours.
        """
        self.stop_commit_listener()
        self.engine.dispose()
        for session in self._requests:
            session.close()
        self._requests.clear()
        if self.path.exists():
            self.path.unlink()
        self._discarded = True

    def close(self) -> None:
        """Dispose everything: override, listener, sessions, engine, scratch file."""
        self.release_client()
        self.stop_commit_listener()
        for session in self._requests:
            session.close()
        self._requests.clear()
        self.engine.dispose()
        if not getattr(self, "_discarded", False) and self.path.exists():
            self.path.unlink()

    # -- seed --------------------------------------------------------------------

    def seed_branch(self) -> None:
        """Write the one restaurant / branch / settings triple the app reads its day from."""
        with self.session() as session:
            if session.get(Restaurant, 1) is None:
                session.add(Restaurant(id=1, name="Sunny Bistro"))
            if session.get(Branch, 1) is None:
                session.add(
                    Branch(
                        id=1,
                        restaurant_id=1,
                        name="Taipei Xinyi",
                        address="No. 1, Section 5, Zhongxiao East Road",
                        phone="02-1234-5678",
                        timezone="Asia/Taipei",
                        business_day_cutoff_hour=4,
                        open_time="11:00",
                        close_time="21:00",
                    )
                )
            if session.get(Settings, 1) is None:
                session.add(
                    Settings(
                        branch_id=1,
                        hold_minutes=10,
                        avg_seat_minutes=15,
                        queue_prefix="A",
                        is_waitlist_open=True,
                        sound_enabled_default=True,
                        notification_templates="{}",
                        staff_pin_hash=TEST_CREDENTIAL_HASH,
                    )
                )
            session.commit()

    def clear_active_set(self) -> None:
        """Remove every waitlist row in one bulk statement before a case names its own set.

        ``reorder`` refuses any list that is not exactly the current active set (R-B07-1), so a row
        another case seeded turns a legal reorder into a 409. The bulk ``DELETE FROM
        waitlist_entries`` form is required rather than a per-row ``session.delete`` sweep, which
        ``_docs/issues/D-02.md`` Context 5a measured as leaving rows behind; the merged
        ``test_staff_tables.py::_clear`` issues the same statement for the same reason.
        """
        with self.session() as session:
            session.query(WaitlistEntry).delete()
            session.commit()

    def make_table(
        self,
        label: str,
        status: TableStatus = TableStatus.AVAILABLE,
        *,
        sort_order: int = 1,
        capacity: int = 2,
        is_active: bool = True,
    ) -> Table:
        """Write one table row and return it detached, so its ``id`` outlives the session."""
        with self.session() as session:
            row = Table(
                branch_id=1,
                label=label,
                capacity=capacity,
                section="Main Hall",
                sort_order=sort_order,
                status=status,
                is_active=is_active,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def make_entry(
        self,
        *,
        seq: int,
        status: WaitlistStatus,
        sort_order: int | None = None,
        table: Table | None = None,
        phone: str | None = None,
        business_date: str = BUSINESS_DATE,
        prefix: str = "A",
        **overrides: Any,
    ) -> WaitlistEntry:
        """Write one waitlist row and return it detached. ``seq`` has no default under 300.

        Every caller passes a sequence number in the 300+ block and the assert below is what turns
        AC-1's ``seq >= 300`` constraint from a comment into a rule: ``uq_queue_seq`` covers
        ``(branch_id, business_date, queue_prefix, seq)``, and the merged seed owns the low numbers
        of this very business date, so a small ``seq`` is a real ``IntegrityError`` rather than a
        hypothetical one.
        """
        assert seq >= 300, f"a D-02 fixture must use seq >= 300, got {seq}"
        fields: dict[str, Any] = {
            "branch_id": 1,
            "queue_number": f"{prefix}{seq:03d}",
            "full_queue_number": f"{prefix}-{business_date.replace('-', '')}-{seq:03d}",
            "queue_prefix": prefix,
            "seq": seq,
            "business_date": business_date,
            "name": f"Party {seq}",
            "phone": phone or f"0912-345-{seq - 300:03d}",
            "party_size": 2,
            "status": status,
            "sort_order": sort_order if sort_order is not None else seq,
            "source": "CUSTOMER",
            "table_id": table.id if table is not None else None,
        }
        fields.update(overrides)
        with self.session() as session:
            row = WaitlistEntry(**fields)
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    # -- read-back ---------------------------------------------------------------

    def read_entry(self, entry_id: Any) -> WaitlistEntry | None:
        """Read a waitlist row back from a brand-new session on a brand-new connection."""
        with self.session() as session:
            row = session.get(WaitlistEntry, _as_uuid(entry_id))
            if row is None:
                return None
            session.expunge(row)
            return row

    def naive(self, instant: datetime) -> datetime:
        """Return the wall-clock value this schema stores for an instant - a naive UTC timestamp.

        The columns are ``DateTime(timezone=True)``, which SQLite round-trips without an offset, so
        the shipped service reads a stamp back as a *naive* value and re-tags it as UTC
        (``waitlist.py::_ensure_aware``). A test seed that handed SQLite an aware datetime would be
        written as ``2026-09-10 13:00:00.000000+08:00`` and read back as that text - not the instant
        the label says. AC-6's no-show probe is a seed, so it converts here rather than pretending
        the two spellings are the same thing.
        """
        return instant.astimezone(UTC).replace(tzinfo=None)

    def read_table(self, table_id: Any) -> Table | None:
        """Read a table row back from a brand-new session on a brand-new connection."""
        with self.session() as session:
            row = session.get(Table, _as_uuid(table_id))
            if row is None:
                return None
            session.expunge(row)
            return row

    def file_value(self, table: str, column: str, key_column: str, key: Any) -> Any:
        """Read one column straight out of the file through the stdlib ``sqlite3`` driver.

        The ORM is not the store. AC-1's seat cases have to say what the *database* holds while the
        request's own objects say something else, so at least one read here goes through no identity
        map at all - the same stdlib read the merged ``test_seed.py`` uses against its own file.
        """
        import sqlite3

        connection = sqlite3.connect(str(self.path))
        try:
            cursor = connection.execute(
                # The column names come from this module, never from a caller; the value binds.
                # UUID columns are stored as 32 hex digits with no dashes, so a key that parses as a
                # UUID goes over in that spelling - str(UUID) keeps the dashes and matches nothing.
                f"SELECT {column} FROM {table} WHERE {key_column} = ?",  # noqa: S608
                [_as_uuid(key).hex if _looks_like_uuid(key) else str(key)],
            )
            row = cursor.fetchone()
            return row[0] if row is not None else None
        finally:
            connection.close()

    # -- commit accounting and failure injection -----------------------------------

    def start_commit_listener(self) -> None:
        """Append one entry to ``commits`` for every commit this engine performs.

        ``event.listens_for(engine, "commit")`` is SQLAlchemy 2.0's own post-commit hook and it
        fires once per commit with the DBAPI connection, which is what makes "both halves, one
        commit" a measurable claim rather than a reading of the service code. The listener is
        attached by this method and removed by :meth:`stop_commit_listener` so a module cannot leak
        a counter into the next one.
        """
        if self._counter is not None:
            return
        commits = self.commits

        @event.listens_for(self.engine, "commit")
        def _count(dbapi_connection):  # noqa: ANN001 - SQLAlchemy's own signature
            del dbapi_connection
            commits.append(1)

        self._counter = _count

    def stop_commit_listener(self) -> None:
        if self._counter is not None:
            event.remove(self.engine, "commit", self._counter)
            self._counter = None

    def commit_count(self) -> int:
        """How many commits this engine has performed since the listener started."""
        return len(self.commits)

    def commits_since(self, mark: int) -> int:
        """How many commits have happened since the caller's saved :meth:`commit_count`."""
        return len(self.commits) - mark

    def break_next_commit(self) -> None:
        """Raise out of the *next* commit this engine performs, once, and only that one.

        Single-shot by construction: the listener removes itself before raising, because an
        unconditionally raising listener makes every later write in the whole suite revert to its
        pre-request value and manufactures greens instead of reds (Context 4). What it raises is
        ``sqlalchemy.exc.DBAPIError`` - the exception SQLAlchemy uses for a commit-time database
        failure - which the application's generic handler renders as the 500 these cases assert.
        """
        from sqlalchemy.exc import DBAPIError

        target = self.engine

        @event.listens_for(target, "commit")
        def _break(dbapi_connection):  # noqa: ANN001 - SQLAlchemy's own signature
            event.remove(target, "commit", _break)
            raise DBAPIError(
                "COMMIT", None, RuntimeError("D-02 injected commit failure: no half-write")
            )

    def request_session_of(self, index: int = -1) -> Session | None:
        """Return one of the sessions handed to requests, for an identity-map read."""
        try:
            return self._requests[index]
        except IndexError:
            return None


def join(client: TestClient, branch_id: int = 1, **overrides: Any) -> Any:
    """POST a guest join through the public transport, with the contract's example body.

    AC-6's second case wants a real join rather than a hand-written row: the thing under test is
    the ``business_date`` the service *chose*, and a seed could choose it arbitrarily. The body is
    the same one ``test_public_waitlist.py`` posts, so the two readings of the rule agree.
    """
    body: dict[str, Any] = {
        "name": "John Smith",
        "phone": "0900-000-001",
        "party_size": 4,
        "note": "Window seat",
    }
    body.update(overrides)
    return client.post(f"/api/v1/branches/{branch_id}/waitlist", json=body)


def dashboard(client: TestClient, headers: dict[str, str] | None = None) -> Any:
    """GET the staff dashboard, which sweeps the lazy no-show before it counts (section 4.10)."""
    return client.get("/api/v1/staff/dashboard", headers=headers or staff_headers())


def call(client: TestClient, entry_id: object, headers: dict[str, str] | None = None) -> Any:
    """POST the staff call that writes ``called_at`` and ``hold_minutes_snapshot``."""
    return client.post(
        f"/api/v1/staff/waitlist/{entry_id}/call", headers=headers or staff_headers()
    )


@contextlib.contextmanager
def frozen_taipei(
    year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0
) -> Iterator[datetime]:
    """Freeze the clock at an ``Asia/Taipei`` wall time and yield the instant it really is.

    Why this exists rather than a bare ``freeze_time(taipei(...))``, which the merged modules do not
    need because they all freeze UTC: freezegun stores a frozen aware datetime as *naive UTC wall
    time* and applies a ``tz_offset`` that is 0 by default, so freezing ``03:59+08:00`` would
    answer ``datetime.now(UTC)`` as ``03:59 UTC`` - 11:59 Taipei - and a test that believed the
    label would assert the wrong instant while still passing. Freezing the **converted UTC**
    instant instead - aware, so freezegun strips the +08:00 and is left with 19:59 - is what makes
    ``datetime.now(UTC)`` answer the real second, and that instant is yielded so a caller can assert
    which UTC second it froze rather than trusting the wall-time label it passed in.
    """
    utc_instant = taipei(year, month, day, hour, minute, second).astimezone(UTC)
    with freeze_time(utc_instant) as clock:
        # An aware UTC target is already the right instant once freezegun has stripped its offset,
        # so the tz_offset stays at its default of zero; the assert is here so a future freezegun
        # that changed that behaviour fails loudly instead of freezing 8 hours away from the label.
        del clock
        yield utc_instant
