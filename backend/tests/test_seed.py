# ruff: noqa
"""Tests for the seed script (backend/app/seed.py)."""

import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo
import sqlite3
import bcrypt

# Helper to run the seed module with given env and args.
def run_seed(db_path: str, reset: bool = False) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "ac",
            "JWT_EXPIRE_HOURS": "1",
            "STAFF_PIN": "0000",
            "ENV": "test",
            "PATH": f"{os.path.expanduser('~')}/.local/bin:{env.get('PATH','')}",
        }
    )
    args = [sys.executable, "-m", "app.seed"]
    if reset:
        args.append("--reset")
    cwd_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return subprocess.run(
        args,
        cwd=cwd_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

# Helper to open sqlite and fetch counts.
def db_counts(db_path: str):
    con = sqlite3.connect(db_path)
    tables = {
        name: con.execute(f"select count(*) from {name}").fetchone()[0]
        for name in [
            "restaurants",
            "branches",
            "settings",
            "tables",
            "waitlist_entries",
        ]
    }
    con.close()
    return tables

# 1. Fresh seed creates schema and correct row counts.
def test_fresh_seed_counts():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    result = run_seed(db_path)
    assert result.returncode == 0, result.stderr
    counts = db_counts(db_path)
    expected = {
        "restaurants": 1,
        "branches": 1,
        "settings": 1,
        "tables": 10,
        "waitlist_entries": 9,
    }
    assert counts == expected

# 2. Restaurant row matches spec.
def test_restaurant_name():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con = sqlite3.connect(db_path)
    name = con.execute("select name from restaurants").fetchone()[0]
    con.close()
    assert name == "Sunny Bistro"

# 3. Branch columns match specification.
def test_branch_values():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con = sqlite3.connect(db_path)
    row = con.execute(
        "select name, address, phone, open_time, close_time, timezone, business_day_cutoff_hour from branches"
    ).fetchone()
    con.close()
    expected = (
        "Taipei Xinyi",
        "No. 123, Example Rd., Xinyi Dist., Taipei City 110, Taiwan",
        "02-1234-5678",
        "11:00",
        "21:00",
        "Asia/Taipei",
        4,
    )
    assert row == expected

# 4. Settings row stores bcrypt hash of PIN 1234 and not env STAFF_PIN.
def test_settings_pin_hash():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con = sqlite3.connect(db_path)
    stored = con.execute("select staff_pin_hash from settings").fetchone()[0]
    con.close()
    assert stored.startswith("$2"), "Not a bcrypt hash"
    assert "1234" not in stored, "Plaintext PIN stored"
    assert bcrypt.checkpw(b"1234", stored.encode()), "Hash does not verify 1234"
    assert not bcrypt.checkpw(b"0000", stored.encode()), "Hash incorrectly verifies env PIN"

# 5. Tables have correct labels, capacities, sections, unique sort_order, activity and status.
def test_tables_structure():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "select label, capacity, section, sort_order, status, is_active from tables order by sort_order"
    ).fetchall()
    con.close()
    want_labels = [f"A{i}" for i in range(1, 5)] + [f"B{i}" for i in range(1, 5)] + [f"C{i}" for i in range(1, 3)]
    capacities = [2] * 4 + [4] * 4 + [6] * 2
    assert [r[0] for r in rows] == want_labels
    assert [r[1] for r in rows] == capacities
    assert all(r[2] == r[0][0] for r in rows)
    assert len({r[3] for r in rows}) == 10
    assert all(r[5] for r in rows)
    status_map = {r[0]: r[4] for r in rows}
    assert status_map["B1"] == "OCCUPIED"
    for lbl, st in status_map.items():
        if lbl != "B1":
            assert st == "AVAILABLE"

# 6. Waitlist entries count and status mix.
def test_waitlist_mix():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con = sqlite3.connect(db_path)
    rows = con.execute("select status from waitlist_entries").fetchall()
    con.close()
    counts = {}
    for (status,) in rows:
        counts[status] = counts.get(status, 0) + 1
    assert len(rows) == 9
    assert counts == {
        "WAITING": 5,
        "CALLED": 1,
        "SEATED": 1,
        "NO_SHOW": 1,
        "CANCELLED": 1,
    }

# 7. Business date is calculated correctly.
def test_business_date():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con = sqlite3.connect(db_path)
    dates = {r[0] for r in con.execute("select business_date from waitlist_entries").fetchall()}
    con.close()
    now_tz = datetime.now(ZoneInfo("Asia/Taipei"))
    expected = (now_tz - timedelta(hours=4)).date().isoformat()
    assert dates == {expected}

# 8. hold_minutes_snapshot is 10 for all entries.
def test_hold_snapshot():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con = sqlite3.connect(db_path)
    values = {r[0] for r in con.execute("select hold_minutes_snapshot from waitlist_entries").fetchall()}
    con.close()
    assert values == {10}

# 9. Queue numbers and full numbers are generated correctly and unique.
def test_queue_numbers():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "select queue_number, seq, queue_prefix, full_queue_number from waitlist_entries"
    ).fetchall()
    con.close()
    q_numbers = [r[0] for r in rows]
    seqs = [r[1] for r in rows]
    prefixes = {r[2] for r in rows}
    full_numbers = {r[3] for r in rows}
    expected_q = [f"A{n:03d}" for n in range(1, 10)]
    assert sorted(q_numbers) == expected_q
    assert sorted(seqs) == list(range(1, 10))
    assert prefixes == {"A"}
    now_tz = datetime.now(ZoneInfo("Asia/Taipei"))
    business = (now_tz - timedelta(hours=4)).date().strftime("%Y%m%d")
    expected_full = {f"A-{business}-{n:03d}" for n in range(1, 10)}
    assert full_numbers == expected_full

# 10. Phones are unique and follow the pattern.
def test_phones_unique():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con = sqlite3.connect(db_path)
    phones = [r[0] for r in con.execute("select phone from waitlist_entries").fetchall()]
    con.close()
    assert len(set(phones)) == 9
    assert phones == [f"0900-000-00{i}" for i in range(1, 10)]

# 11. CALLED entry timestamp is between 60 and 300 seconds ago.
def test_called_timestamp_age():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con = sqlite3.connect(db_path)
    row = con.execute("select called_at from waitlist_entries where status='CALLED'").fetchone()
    con.close()
    assert row and row[0]
    ts = datetime.fromisoformat(row[0].replace(" ", "T"))
    if ts.tzinfo is None:
        # SQLite stores DateTime(timezone=True) as a naive UTC string (same
        # assumption AC-8 makes): re-attach UTC before comparing.
        ts = ts.replace(tzinfo=UTC)
    age = (datetime.now(UTC) - ts).total_seconds()
    assert 60 <= age <= 300

# 12. SEATED entry links to B1 and B1 is OCCUPIED.
def test_seated_table_link():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con = sqlite3.connect(db_path)
    seated = con.execute(
        "select table_id from waitlist_entries where status='SEATED'"
    ).fetchone()[0]
    label = con.execute("select label from tables where id=?", (seated,)).fetchone()[0]
    status = con.execute("select status from tables where id=?", (seated,)).fetchone()[0]
    con.close()
    assert label == "B1"
    assert status == "OCCUPIED"

# 13. Idempotent run without --reset skips seeding.
def test_idempotent_skip_message():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    result = run_seed(db_path)
    assert result.returncode == 0
    msg = result.stdout.lower()
    assert "skip" in msg or "already" in msg

# 14. --reset clears and reseeds with new IDs.
def test_reset_creates_new_ids():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con1 = sqlite3.connect(db_path)
    ids_before = tuple(
        con1.execute("select id from waitlist_entries order by id").fetchall()
    )
    con1.close()
    result = run_seed(db_path, reset=True)
    assert result.returncode == 0
    assert "reset" in result.stdout.lower()
    con2 = sqlite3.connect(db_path)
    ids_after = tuple(
        con2.execute("select id from waitlist_entries order by id").fetchall()
    )
    con2.close()
    assert ids_before != ids_after

# 15. Hand-made drift rows are removed by --reset.
def test_reset_removes_drift():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db.name
    db.close()
    run_seed(db_path)
    con = sqlite3.connect(db_path)
    con.execute(
        "insert into tables (id, branch_id, label, capacity, section, sort_order, status, is_active, created_at, updated_at) "
        "values ('zzz', 1, 'Z9', 8, 'Z', 99, 'AVAILABLE', 1, '2026-09-10 00:00:00', '2026-09-10 00:00:00')"
    )
    con.execute("delete from waitlist_entries where status='NO_SHOW'")
    con.commit()
    con.close()
    result = run_seed(db_path, reset=True)
    assert result.returncode == 0
    con2 = sqlite3.connect(db_path)
    left = con2.execute("select count(*) from tables where label='Z9'").fetchone()[0]
    noshow = con2.execute("select count(*) from waitlist_entries where status='NO_SHOW'").fetchone()[0]
    con2.close()
    assert left == 0
    assert noshow == 1
