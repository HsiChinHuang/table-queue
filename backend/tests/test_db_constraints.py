"""AC-5 (D-02): the unique-constraint surface at database level, including the rule that is absent.

Two of the three rules ``app/models.py`` declares were already exercised - ``test_models.py`` holds
``test_unique_table_label_per_branch`` and ``test_unique_branch_one_to_one_settings`` - and the
third, ``uq_queue_seq`` over ``(branch_id, business_date, queue_prefix, seq)``, was exercised by
nothing at all. Its only adjacent evidence was incidental: ``test_public_waitlist`` stores two rows
both numbered ``A001`` under two business dates and so demonstrates the *non*-collision half by
accident, with no assertion anywhere standing behind the collision half. These three cases close
that gap.

The second thing this module has to get right is its own shape. A ``pytest.raises(IntegrityError)``
block can be a dead assertion: ``session.add()`` accepts a colliding row happily, and a case that
never reaches the database - never flushes, never commits - can never raise. So every case below
takes its row to the database in a session it owns and names the constraint text it expected, which
is what turns "it raised" into "the database enforced this key, on these columns, for this reason".
The third case is a negative one: it asserts that no unique rule exists on ``phone``, so the day
somebody adds one this case goes red and the schema decision comes back to this issue instead of
shipping silently (Out of scope 2 watches for exactly that change).

Rows are seeded with ``seq >= 300`` because the merged seed owns the low numbers of business date
``2026-09-10`` and this file's first two cases collide on purpose.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import WaitlistEntry, WaitlistStatus
from tests._db_test_support import Database

PREFIX = "A"
BUSINESS_DAY = "2026-09-10"
NEXT_DAY = "2026-09-11"


def _entry(seq: int, business_date: str, phone: str) -> WaitlistEntry:
    """Build - but do not write - one row on the ``(branch, day, prefix, seq)`` key under test."""
    return WaitlistEntry(
        branch_id=1,
        queue_number=f"{PREFIX}{seq:03d}",
        full_queue_number=f"{PREFIX}-{business_date.replace('-', '')}-{seq:03d}",
        queue_prefix=PREFIX,
        seq=seq,
        business_date=business_date,
        name="Constraint Case",
        phone=phone,
        party_size=2,
        status=WaitlistStatus.WAITING,
        sort_order=seq,
        source="CUSTOMER",
    )


@pytest.fixture()
def db():
    """This file's own SQLite schema, rebuilt per case and unlinked on teardown."""
    database = Database("d02_constraints")
    database.seed_branch()
    try:
        yield database
    finally:
        database.close()


def test_uq_queue_seq_rejects_a_duplicate_branch_date_prefix_seq(db: Database) -> None:
    """The collision half of the key specs 8 and 14 both name - enforced by SQLite, not by Python.

    ``next_seq`` hands out ``max(seq) + 1``, so a collision should never happen; the constraint is
    the net that catches the case where it does (two staff screens reading the same top of the
    queue), and Out of scope 3's claim today is exactly "the net holds, and there is no retry". The
    colliding row is added in a session of the case's own and taken to the database with a real
    ``commit()``, because an ``add()`` alone reaches nothing: the constraint lives in the file, so
    only the file may refuse the row. The message is asserted as well as the exception. SQLite
    reports a named table constraint under the words ``UNIQUE constraint failed`` plus the four
    qualified column names, so the assertion is on those four - all of them, which is what
    identifies *this* key rather than ``uq_branch_label`` or the one-to-one ``settings`` rule
    firing by mistake.
    """
    db.make_entry(seq=350, status=WaitlistStatus.WAITING, business_date=BUSINESS_DAY, prefix=PREFIX)
    session = db.session()
    try:
        session.add(_entry(350, BUSINESS_DAY, "0912-777-350"))
        with pytest.raises(IntegrityError) as raised:
            session.commit()
        message = str(raised.value)
        assert "UNIQUE constraint failed" in message
        for column in ("branch_id", "business_date", "queue_prefix", "seq"):
            assert f"waitlist_entries.{column}" in message
    finally:
        session.close()

    # The refusal was the second row's: the row that got there first is still the only one.
    session = db.session()
    try:
        assert session.query(WaitlistEntry).filter_by(seq=350).count() == 1
    finally:
        session.close()


def test_uq_queue_seq_allows_the_same_seq_on_the_next_business_date(db: Database) -> None:
    """The non-collision half, which is what makes ``uq_queue_seq`` a *key* and not a column.

    ``seq`` 351 twice, once per business date, must be two rows: the queue restarts its numbering
    every service, so ``A-20260910-351`` and ``A-20260911-351`` coexist and nothing about either is
    special. Today that only happens by accident inside an injected-clock test with no assertion
    behind it, which is why this case states it directly - a rule that "uniquified" ``seq`` alone
    would break every queue that survives one midnight, and only a case like this would notice.

    The two writes go through the same session the first one is committed on: the second
    ``commit()`` is the statement at issue, and it must **not** raise.
    """
    session: Session = db.session()
    try:
        session.add(_entry(351, BUSINESS_DAY, "0912-777-351"))
        session.commit()
        session.add(_entry(351, NEXT_DAY, "0912-777-352"))
        session.commit()  # the whole case: a key that spans days must let this one through
        stored = (
            session.query(WaitlistEntry)
            .filter_by(seq=351)
            .order_by(WaitlistEntry.business_date)
            .all()
        )
        assert [row.business_date for row in stored] == [BUSINESS_DAY, NEXT_DAY]
        assert [row.full_queue_number for row in stored] == ["A-20260910-351", "A-20260911-351"]
    finally:
        session.close()


def test_no_unique_rule_exists_on_phone(db: Database) -> None:
    """A negative case on purpose: the duplicate-phone rule is a pre-check, and it is not a key.

    ``services/waitlist.py:453-461`` reads ``active_entry_for_phone`` and then raises
    ``WAITLIST_DUPLICATE_PHONE`` - an ordinary ``commit()`` follows, with no ``IntegrityError`` to
    rescue and nothing to retry, which is why Out of scope 2 refuses to write a race test against
    machinery that does not exist. The claim asserted here is therefore about the **schema**: two
    identical numbers committed back to back must be accepted, both rows present afterwards, or the
    day a ``UniqueConstraint`` or a ``unique=True`` lands on ``phone`` this case goes red and the
    decision (unique index? ``SELECT ... FOR UPDATE``? an advisory lock?) comes back through this
    issue instead of arriving as a production 500.

    The two rows deliberately differ in every column the queue key covers except the phone, and
    their ``seq`` values are distinct, so a green here cannot come from ``uq_queue_seq`` declining
    to fire for an unrelated reason.
    """
    session: Session = db.session()
    try:
        session.add(_entry(352, BUSINESS_DAY, "0912-345-000"))
        session.commit()  # the commit is the claim: nothing refuses this number
        session.add(_entry(353, BUSINESS_DAY, "0912-345-000"))
        session.commit()  # ... and nothing refuses this one either, identical phone and all
        stored = session.query(WaitlistEntry).filter_by(phone="0912-345-000").all()
        assert sorted(row.seq for row in stored) == [352, 353]
    finally:
        session.close()

    # The schema itself agrees: no index, no unique column, and no multi-column rule names phone.
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    columns = inspector.get_columns("waitlist_entries")
    phone_column = next(column for column in columns if column["name"] == "phone")
    assert phone_column.get("unique", False) in (None, False)
    # SQLite spells an inline column-level UNIQUE as an unnamed table constraint and only names the
    # multi-column ones, so this reads the constraint **column sets** and expects phone in none of
    # them. ``uq_branch_label`` lives on ``tables`` - the other named rule in the model - and is
    # read from there so the pair the model declares is both accounted for.
    entry_constraints = {
        tuple(constraint["column_names"] or ())
        for constraint in inspector.get_unique_constraints("waitlist_entries")
    }
    assert ("branch_id", "business_date", "queue_prefix", "seq") in entry_constraints
    assert not [columns for columns in entry_constraints if "phone" in columns]
    table_constraints = {
        constraint["name"]: tuple(constraint["column_names"] or ())
        for constraint in inspector.get_unique_constraints("tables")
    }
    assert table_constraints.get("uq_branch_label") == ("branch_id", "label")
    assert not [
        index
        for index in inspector.get_indexes("waitlist_entries")
        if index["unique"] and "phone" in (index["column_names"] or [])
    ]
