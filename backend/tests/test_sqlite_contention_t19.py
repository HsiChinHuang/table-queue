"""t19 (platform issue #74): SQLite store contention is a contract outcome.

The acceptance gate for this issue is the ``## Verification commands`` section of
``docs/issues/t19.md``; these tests mirror those probes one-for-one so the suite itself
watches the contract:

* AC-1 - a concurrent external writer (a second ``sqlite3`` connection holding
  ``BEGIN EXCLUSIVE``) makes the guest join answer the typed 503 ``STORE_BUSY`` with a
  ``Retry-After`` header and the contract envelope, the board read answers 200 or the
  same typed 503, zero 500s, and the store is healthy after the lock clears.
* AC-2 - the per-request busy timeout is a documented named value in 0.5..10s at the
  engine config site (static arm, in-process) and a blocked write fails fast inside it
  (measured arm, subprocess probe).
* AC-3 - the app-created store runs in WAL journal mode (``PRAGMA journal_mode`` is
  ``wal``), so readers no longer block behind the writer.
* AC-4 - the write-on-GET path (the staff-list read's lazy no-show sweep) raises the
  typed 503 ``AppError`` under a held lock - never the raw SQLite lock error - and the
  sweep still persists after the lock clears.

The probe arms run in a subprocess against a scratch database the app's own lifespan
creates, for the same reason the issue's blocks do: the app's engine is built once at
import time from ``DATABASE_URL``, so re-pointing it in-process would change nothing.
Each probe prints ``PROBE_OK`` / ``MEASURED_OK`` / ``WAL_OK`` and exits 0 only when
every arm of its AC holds.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

PROBE_ENV_OVERRIDES = {
    "JWT_SECRET": "t19-probe-secret-0123456789-abcdefghijklmnopqrstuvwxyz",
    "STAFF_PIN": "0000",
    "ENV": "development",
    "TZ": "UTC",
}

AC1_SCRIPT = r'''import logging, os, re, sqlite3, sys, time, warnings
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

def load_catalog():
    """Parse the section 11 error-code table (code -> http status) from _docs/specs.md."""
    text = open("../_docs/specs.md", encoding="utf-8").read()
    m = re.search(r"^## 11\..*?(?=^## )", text, re.S | re.M)
    if not m:
        return None
    return dict(re.findall(r"^([A-Z][A-Z0-9_]+)\s+(\d{3})\s", m.group(0), re.M)) or None

def retryable_problems(resp, cat):
    """Problems with a response that the AC says must be the typed retryable 503."""
    if resp.status_code != 503:
        return ["status is %d, want the retryable 503" % resp.status_code]
    problems = []
    ra = resp.headers.get("Retry-After")
    if ra is None:
        problems.append("no Retry-After header")
    else:
        try:
            v = int(ra)
            if not 1 <= v <= 30:
                problems.append("Retry-After is %r, want integer seconds in 1..30" % ra)
        except ValueError:
            problems.append("Retry-After is %r, want integer seconds" % ra)
    try:
        body = resp.json()
    except Exception:
        problems.append("body is not JSON")
        return problems
    if not isinstance(body, dict) or set(body) != {"error"}:
        what = sorted(body) if isinstance(body, dict) else type(body).__name__
        problems.append("top level is %r, want exactly the 'error' key" % what)
        return problems
    err = body["error"]
    if not isinstance(err, dict):
        problems.append("error is not an object")
        return problems
    if "detail" in body or "detail" in err:
        problems.append("a framework-default 'detail' key leaked through")
    code = err.get("code")
    if not isinstance(code, str) or not code:
        problems.append("error.code is missing or not a non-empty string")
    elif code == "INTERNAL_ERROR":
        problems.append(
            "error.code is INTERNAL_ERROR (the 500 crash code), not a retryable contract code"
        )
    elif cat.get(code) != "503":
        problems.append(
            "error.code %s is not a 503 row in the _docs/specs.md section 11 table (row: %r)"
            % (code, cat.get(code))
        )
    if not isinstance(err.get("message"), str) or not err.get("message"):
        problems.append("error.message is missing or not a non-empty string")
    if "details" in err and not isinstance(err["details"], dict):
        problems.append("error.details is present but not an object")
    return problems

def hold_lock(dbfile):
    """The external writer: a second connection holding BEGIN EXCLUSIVE (deterministic)."""
    lock = sqlite3.connect(dbfile, timeout=5)
    lock.isolation_level = None
    lock.execute("begin exclusive")
    sanity = sqlite3.connect(dbfile, timeout=1)
    try:
        sanity.execute(
            "insert into restaurants (id, name, created_at, updated_at) "
            "values (999999, 'probe-sanity', '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
        )
        sanity.rollback()
        raise SystemExit(
            "probe sanity failed: a write SUCCEEDED under the held exclusive lock - "
            "the lock is not effective"
        )
    except sqlite3.OperationalError:
        pass
    finally:
        sanity.close()
    return lock

cat = load_catalog()
if not cat:
    print("could not parse the section 11 error-code table from _docs/specs.md")
    sys.exit(1)

from fastapi.testclient import TestClient
from app.main import app

dbfile = os.environ["DATABASE_URL"].replace("sqlite:///", "")
problems = []
fives = 0

with TestClient(app, raise_server_exceptions=False) as c:
    lock = hold_lock(dbfile)
    phone1 = "09%08d" % (int(time.time()) % 10**8)
    phone2 = "09%08d" % (int(time.time() + 1234567) % 10**8)

    rw = c.post(
        "/api/v1/branches/1/waitlist",
        json={"name": "Probe", "phone": phone1, "party_size": 1},
    )
    pw = retryable_problems(rw, cat)
    if pw:
        msg = "write (guest join) under held lock: " + "; ".join(pw)
        problems.append(msg + " (body=%r)" % rw.text[:160])
    if rw.status_code == 500:
        fives += 1

    rr = c.get("/api/v1/public/branches/1/board")
    if rr.status_code == 500:
        fives += 1
        problems.append(
            "read (public board) under held lock answered 500 (body=%r)" % rr.text[:160]
        )
    elif rr.status_code == 503:
        pr = retryable_problems(rr, cat)
        if pr:
            msg = "read (public board) under held lock: " + "; ".join(pr)
            problems.append(msg + " (body=%r)" % rr.text[:160])
    elif rr.status_code != 200:
        problems.append(
            "read (public board) under held lock answered %d, want 200 or the typed 503"
            % (rr.status_code, rr.text[:160])
        )

    lock.execute("commit")
    lock.close()

    ro = c.get("/api/v1/public/branches/1/board")
    if ro.status_code != 200:
        problems.append(
            "recovery: board after lock release answered %d, want 200 (body=%r)"
            % (ro.status_code, ro.text[:160])
        )
    rw2 = c.post(
        "/api/v1/branches/1/waitlist",
        json={"name": "Probe", "phone": phone2, "party_size": 1},
    )
    if rw2.status_code not in (200, 201):
        problems.append(
            "recovery: guest join after lock release answered %d, want 20x (body=%r)"
            % (rw2.status_code, rw2.text[:160])
        )

if fives:
    problems.append(
        "%d response(s) answered 500 under contention - the silent-500 gap (B-4) is still open"
        % fives
    )
if problems:
    for p in problems:
        print("  " + p)
    sys.exit(1)
print("PROBE_OK")
'''

AC2_SCRIPT = r'''import logging, os, sqlite3, sys, time, warnings
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

from fastapi.testclient import TestClient
from app.main import app

dbfile = os.environ["DATABASE_URL"].replace("sqlite:///", "")
with TestClient(app, raise_server_exceptions=False) as c:
    lock = sqlite3.connect(dbfile, timeout=5)
    lock.isolation_level = None
    lock.execute("begin exclusive")
    sanity = sqlite3.connect(dbfile, timeout=1)
    try:
        sanity.execute(
            "insert into restaurants (id, name, created_at, updated_at) "
            "values (999999, 'probe-sanity', '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
        )
        sanity.rollback()
        raise SystemExit(
            "probe sanity failed: a write SUCCEEDED under the held exclusive lock - "
            "the lock is not effective"
        )
    except sqlite3.OperationalError:
        pass
    finally:
        sanity.close()
    phone = "09%08d" % (int(time.time()) % 10**8)
    t0 = time.monotonic()
    r = c.post(
        "/api/v1/branches/1/waitlist",
        json={"name": "Probe", "phone": phone, "party_size": 1},
    )
    elapsed = time.monotonic() - t0
    lock.execute("commit")
    lock.close()
print("blocked write: status %d after %.2fs" % (r.status_code, elapsed))
if elapsed < 0.2:
    raise SystemExit(
        "the blocked write answered in %.2fs - the held lock did not block it (probe anomaly)"
        % elapsed
    )
if elapsed >= 15:
    raise SystemExit(
        "the worker parked %.2fs under the held lock - the legacy 30s park is still in effect"
        % elapsed
    )
print("MEASURED_OK")
'''

AC3_SCRIPT = r'''import os, sqlite3, sys, warnings
warnings.filterwarnings("ignore")

from app.main import app  # noqa: F401 - importing the app registers every model on Base
from app.database import Base, engine

Base.metadata.create_all(bind=engine)
engine.dispose()
dbfile = os.environ["DATABASE_URL"].replace("sqlite:///", "")
con = sqlite3.connect(dbfile)
mode = con.execute("pragma journal_mode").fetchone()[0]
con.close()
print("journal_mode:", mode)
if str(mode).lower() == "wal":
    print("WAL_OK")
    sys.exit(0)
sys.exit(3)
'''

AC4_SCRIPT = r'''import logging, os, re, sqlite3, sys, time, uuid, warnings
from datetime import timedelta
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

def load_catalog():
    """Parse the section 11 error-code table (code -> http status) from _docs/specs.md."""
    text = open("../_docs/specs.md", encoding="utf-8").read()
    m = re.search(r"^## 11\..*?(?=^## )", text, re.S | re.M)
    if not m:
        return None
    return dict(re.findall(r"^([A-Z][A-Z0-9_]+)\s+(\d{3})\s", m.group(0), re.M)) or None

def hold_lock(dbfile):
    """The external writer: a second connection holding BEGIN EXCLUSIVE (deterministic)."""
    lock = sqlite3.connect(dbfile, timeout=5)
    lock.isolation_level = None
    lock.execute("begin exclusive")
    sanity = sqlite3.connect(dbfile, timeout=1)
    try:
        sanity.execute(
            "insert into restaurants (id, name, created_at, updated_at) "
            "values (999999, 'probe-sanity', '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
        )
        sanity.rollback()
        raise SystemExit(
            "probe sanity failed: a write SUCCEEDED under the held exclusive lock - "
            "the lock is not effective"
        )
    except sqlite3.OperationalError:
        pass
    finally:
        sanity.close()
    return lock

cat = load_catalog()
if not cat:
    print("could not parse the section 11 error-code table from _docs/specs.md")
    sys.exit(1)

from fastapi.testclient import TestClient
from app.main import app

dbfile = os.environ["DATABASE_URL"].replace("sqlite:///", "")

with TestClient(app, raise_server_exceptions=False) as c:
    login = c.post("/api/v1/auth/login", json={"pin": "0000"})
    if login.status_code != 200:
        print("staff login failed: %d %r" % (login.status_code, login.text[:200]))
        sys.exit(1)
    h = {"Authorization": "Bearer " + login.json()["access_token"]}

    from app.database import Base, engine
    from app.models import Branch, WaitlistEntry, WaitlistSource, WaitlistStatus
    from app.services.waitlist import business_date_for, utc_now
    from app.services.staff_waitlist import list_waitlist
    from app.errors import AppError
    from sqlalchemy.orm import Session
    with Session(engine) as s:
        branch = s.get(Branch, 1)
        now = utc_now()
        day = business_date_for(branch, now)
        entry = WaitlistEntry(
            id=uuid.uuid4(),
            branch_id=1,
            queue_number="A1",
            full_queue_number="A1-%d" % (int(time.time()) % 10**6),
            queue_prefix="A",
            seq=1,
            business_date=day,
            name="Lapsed",
            phone="0955550001",
            party_size=1,
            status=WaitlistStatus.CALLED,
            sort_order=1,
            source=WaitlistSource.CUSTOMER,
            hold_minutes_snapshot=10,
            created_at=now - timedelta(minutes=15),
            updated_at=now - timedelta(minutes=15),
            called_at=now - timedelta(minutes=15),
        )
        s.add(entry)
        s.commit()
        eid = str(entry.id)
    print(
        "seeded lapsed CALLED row %s (business_date=%s, called 15 min ago, 10 min hold)"
        % (eid, day)
    )

    # Stage 1: under the held lock the staff-list read path must not leak the raw SQLite
    # lock error (the 500 path, B-4). The read path is probed at the service level
    # (list_waitlist on a fresh session) because the HTTP staff GET answers 401 under the
    # lock via the auth verifier's own database read (see the issue Context).
    lock = hold_lock(dbfile)

    try:
        with Session(engine) as s2:
            list_waitlist(s2, now=utc_now(), status="ALL")
        print(
            "  under held lock the staff-list read completed cleanly (read path no longer writes "
            "/ reads unblocked)"
        )
    except AppError as e:
        if e.status_code != 503 or cat.get(e.code) != "503":
            print(
                "  the staff-list read under held lock raised AppError %s (status %s), want the "
                "typed 503 with a section-11 503 row (row: %r)"
                % (e.code, e.status_code, cat.get(e.code))
            )
            sys.exit(1)
        print("  under held lock the staff-list read raised the typed 503 AppError %s" % e.code)
    except Exception as e:
        name = type(e).__name__
        print(
            "  the staff-list read under held lock leaked %s: %s - the raw SQLite lock error "
            "must become the typed 503, the 500 path (B-4)" % (name, str(e)[:160])
        )
        sys.exit(1)
    lock.execute("commit")
    lock.close()

    # Stage 2: after release the store is healthy and the section 4.10 sweep still persists.
    r2 = c.get("/api/v1/staff/waitlist", params={"status": "ALL"}, headers=h)
    if r2.status_code != 200:
        print(
            "  staff-list GET after lock release answered %d, want 200 (body=%r)"
            % (r2.status_code, r2.text[:160])
        )
        sys.exit(1)

    def status_of(resp):
        try:
            for it in resp.json().get("items", []):
                if str(it.get("id")) == eid:
                    return it.get("status")
        except Exception:
            pass
        return None

    st = status_of(r2)
    if st != "NO_SHOW":
        phone = "09%08d" % (int(time.time()) % 10**8)
        j = c.post(
            "/api/v1/branches/1/waitlist",
            json={"name": "Probe", "phone": phone, "party_size": 1},
        )
        if j.status_code not in (200, 201):
            print(
                "  recovery join after lock release answered %d (body=%r)"
                % (j.status_code, j.text[:160])
            )
            sys.exit(1)
        r3 = c.get("/api/v1/staff/waitlist", params={"status": "ALL"}, headers=h)
        if r3.status_code != 200:
            print("  staff-list GET after recovery join answered %d, want 200" % r3.status_code)
            sys.exit(1)
        st = status_of(r3)
        if st != "NO_SHOW":
            print(
                "  the lapsed CALLED row still reads %r, want NO_SHOW - the section 4.10 sweep "
                "is not request-driven (staff-list read or join write)" % st
            )
            sys.exit(1)
print("PROBE_OK")
'''


def _run_probe(name: str, script: str, timeout: int = 180) -> str:
    """Run one probe script in a subprocess against a scratch store, and clean it up.

    The scratch file lives under the backend directory (the probe's own relative
    ``DATABASE_URL``), and is removed on every exit path - including a failing probe -
    so no probe state survives into the next test or the next run.
    """
    env = os.environ.copy()
    env.update(PROBE_ENV_OVERRIDES)
    env["DATABASE_URL"] = f"sqlite:///./{name}.db"
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    for suffix in ("", "-wal", "-shm"):
        path = BACKEND_DIR / f"{name}.db{suffix}"
        if path.exists():
            path.unlink()
    assert proc.returncode == 0, (
        "probe " + name + " failed (rc=" + str(proc.returncode) + "):"
        + "\n" + proc.stdout + "\n" + proc.stderr
    )
    return proc.stdout


def test_ac1_held_lock_write_answers_typed_503_with_zero_500s() -> None:
    """AC-1: under a held ``BEGIN EXCLUSIVE`` the write is the typed 503, never a 500.

    The probe asserts the full contract on the way: the 503 carries ``Retry-After`` in
    integer seconds 1..30, the body is exactly the ``error`` envelope, ``error.code``
    is a 503 row of the specs.md section 11 table (not ``INTERNAL_ERROR``), the board
    read under the same lock answers 200 or the same typed 503, nothing answers 500,
    and after the lock clears the board answers 200 and a join answers 20x.
    """
    out = _run_probe("_t19test_ac1", AC1_SCRIPT)
    assert "PROBE_OK" in out


def test_ac2_busy_timeout_is_documented_named_and_sub_30s() -> None:
    """AC-2: the busy timeout is a documented named value in 0.5..10s, and it bounds the park.

    Static arm (in-process): the legacy literal 30 is gone from the engine config site,
    the binding is the named ``SQLITE_BUSY_TIMEOUT`` constant, its value is in the
    documented 0.5..10s window, and the binding's site carries the busy/lock semantics.
    Measured arm (subprocess): a write blocked by a held exclusive lock answers after
    at least 0.2s (the lock really held it) and well under the 15s that the legacy 30s
    park used to cost.
    """
    db_src = (BACKEND_DIR / "app" / "database.py").read_text(encoding="utf-8")
    assert '"timeout": 30' not in db_src, "the legacy literal 30 is still bound as the busy timeout"
    assert "SQLITE_BUSY_TIMEOUT" in db_src, "the busy timeout is not bound to a named value"

    from app.database import SQLITE_BUSY_TIMEOUT

    assert 0.5 <= SQLITE_BUSY_TIMEOUT <= 10, (
        f"the busy timeout {SQLITE_BUSY_TIMEOUT}s is outside the documented 0.5..10s window"
    )

    lines = db_src.splitlines()
    idx = next(i for i, line in enumerate(lines) if "SQLITE_BUSY_TIMEOUT" in line)
    window = " ".join(lines[max(0, idx - 30) : idx + 30]).lower()
    assert re.search(r"busy|lock|contention", window), (
        "the busy-timeout binding carries no documentation of the busy/lock semantics at its site"
    )

    out = _run_probe("_t19test_ac2", AC2_SCRIPT)
    assert "MEASURED_OK" in out


def test_ac3_app_created_store_runs_in_wal() -> None:
    """AC-3: the journal-mode decision is explicit - the app-created store runs in WAL.

    The probe imports the app (registering every model), builds the schema on the
    app's own engine, and reads ``PRAGMA journal_mode`` back off the file: it must be
    ``wal``, so a reader no longer blocks behind the writer for the busy timeout.
    """
    out = _run_probe("_t19test_ac3", AC3_SCRIPT)
    assert "WAL_OK" in out


def test_ac4_staff_list_read_path_is_contention_safe_and_sweep_persists() -> None:
    """AC-4: the write-on-GET path never leaks the raw lock error, and the sweep persists.

    With a lapsed ``CALLED`` row seeded, the service-level staff-list read under a
    held ``BEGIN EXCLUSIVE`` raises the typed 503 ``AppError`` (its code a 503 row of
    the specs.md section 11 table) - or completes - and never the raw SQLite lock
    error. After the lock clears, the HTTP staff-list read answers 200 and the seeded
    row reads back ``NO_SHOW``: the section 4.10 transition stays request-driven.
    """
    out = _run_probe("_t19test_ac4", AC4_SCRIPT)
    assert "PROBE_OK" in out
