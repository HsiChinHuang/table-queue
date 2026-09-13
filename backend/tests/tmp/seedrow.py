'''Shared row seeder for the T9 AC probes (written under $TMPDIR by each block, imported by path).

Writes exactly one settings row through raw SQL so the probe never depends on the bootstrap under
test. Every NOT NULL column is named because bootstrap_defaults' own INSERT had to name them too
(B-15: a Python-side default never applies to a raw text() INSERT).
'''
import bcrypt
from sqlalchemy import text

GOOD_PIN = "4321"


def seed_hashed_row(db, pin=GOOD_PIN, extra_cols=None):
    h = bcrypt.hashpw(pin.encode(), bcrypt.gensalt(rounds=12)).decode()
    cols = ("id, branch_id, hold_minutes, avg_seat_minutes, queue_prefix, is_waitlist_open, "
            "sound_enabled_default, notification_templates, staff_pin_hash, created_at, updated_at")
    vals = "1, 1, 10, 15, 'A', 1, 1, '{}', :h, '2026-01-01 00:00:00', '2026-01-01 00:00:00'"
    if extra_cols:
        cols += ", " + ", ".join(c for c, _ in extra_cols)
        vals += ", " + ", ".join(v for _, v in extra_cols)
    db.execute(text("insert into settings (" + cols + ") values (" + vals + ")"), {"h": h})
    db.commit()
    return h


def seed_hashed_row_on_existing(db, pin=GOOD_PIN):
    """Overwrite the single settings row's hash, whatever put it there (bootstrap or not)."""
    h = bcrypt.hashpw(pin.encode(), bcrypt.gensalt(rounds=12)).decode()
    db.execute(text("update settings set staff_pin_hash=:h where id=1"), {"h": h})
    db.commit()
    return h
