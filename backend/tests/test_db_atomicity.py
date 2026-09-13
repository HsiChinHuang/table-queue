"""AC-1 (D-02): the both-or-neither property of the release and seat paths.

The stub asked for "transaction rollback on error", "release table transaction" and "seat
transaction (entry + table atomic)". The shipped write paths open no nested transaction and never
call ``rollback`` - ``services/tables.py::release_table`` and
``services/staff_waitlist.py::seat_entry`` each write both rows on one session and issue exactly
**one** ``commit()`` (specs section 14 says exactly that). What these cases therefore test is not
"did somebody roll back" but **"did the database move both rows, or neither"**, and the failure is
injected through SQLAlchemy 2.0's own ``commit`` engine event rather than through a pool or dispose
trick (D-01 Out of scope 4: this engine is ``NullPool`` and has no shutdown path).

Six named cases, no more and no fewer, and AC-1's counts over them are 3 passed / 3 xfailed / 0
xpassed / 0 failed. Every one of those numbers is measured rather than assumed, and the file keeps
itsself at six by making the running side do double duty rather than by dropping a claim AC-1 names.

- the two happy paths, each asserting its own commit count is exactly **1** - the shape section 14
  promises, measured on this engine as ``RELEASE_COMMITS=1``;
- the release path with that one commit broken: 500, and both rows unchanged in the store;
- the seat path with the same injection, which is where the file's finding lives. Context 4
  predicted the autoflushed ``UPDATE``s would reach the file while its commit was broken and leave
  the store holding half a seat; the injected failure aborts that transaction instead, and the file
  is never
  given either half. What survives is the request's own identity map, which reads ``SEATED`` /
  ``OCCUPIED`` and is the thing Context 4 reported as the store. So the case states both readings -
  the store moved neither row, and one session is now lying about a seat - and adds a third reading
  that cannot be faked from an identity map: the broken transaction still holds the file's write
  lock, so nothing can write it at all. ``_atomicity_probe.py`` beside this module prints the first
  two readings for anyone who wants to see the trap rather than take it on faith; it is a probe and
  not a seventh case, because AC-1's counts are a contract about the file as well as about the code;
- **three** ``xfail(run=False)`` bodies holding the three forbidden outcomes AC-1 names: the two
  half-writes section 14 bars, and the seat-side pairing AC-1 excludes by name because it
  **xpassed** under the harness. An XPASS on any of them is a deliberate red, because it would mean
  a forbidden half-write had become reachable through the API rather than through a test helper.

The third xfail is the one worth reading before editing. AC-1 names the id, excludes it two
sentences later, and counts three xfailed bodies anyway; the pairing is reachable only by writing
one row past the service, and a body handed that helper would go green on the forbidden pair and
report an XPASS that reads like a broken seat path when the only defect in the room is the helper.
Tests must not be able to manufacture their own reds, so those bodies read a pair the seed committed
together and nothing else.

Fixtures here use ``seq >= 300`` (``_db_test_support.Database.make_entry`` asserts it) because
``uq_queue_seq`` is ``(branch_id, business_date, queue_prefix, seq)`` and the merged seed already
owns the low numbers of business date ``2026-09-10``.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.models import Table, TableStatus, WaitlistEntry, WaitlistStatus
from tests._db_test_support import Database, staff_headers

REL = "/api/v1/staff/tables/%s/release"
SEAT = "/api/v1/staff/waitlist/%s/seat"


@pytest.fixture()
def db():
    """One SQLite file for this case: schema, branch seed, commit counter, teardown."""
    database = Database("d02_atomicity")
    database.seed_branch()
    database.start_commit_listener()
    try:
        yield database
    finally:
        database.close()


def _release(client: TestClient, table_id: object) -> object:
    """POST the release of one table as a staff caller."""
    return client.post(REL % table_id, headers=staff_headers())


def _seat(client: TestClient, entry_id: object, table_id: object) -> object:
    """POST one entry onto one table as a staff caller."""
    return client.post(
        SEAT % entry_id, json={"table_id": str(table_id)}, headers=staff_headers()
    )


def test_release_writes_both_halves_in_one_commit(db: Database) -> None:
    """Section 14's release: table ``AVAILABLE``, party ``DONE`` with ``closed_at``, one commit.

    Both halves are read back through a session the request never used, and the commit count comes
    off the engine's own ``commit`` event rather than from a reading of the service code. The count
    is scoped to the request - the fixture's seed commits are already on the books - so the number
    this case pins is the release's own. A refactor that wrote the two rows in two commits would
    fail here on the count while still landing both rows, which is the half a row-only test
    misses. The
    response body and ``closed_at`` are what the sibling modules already assert; the pair of
    transitions and their single commit are what this file is for, and each case here keeps to that
    seam so a failure says which guarantee broke.
    """
    table, entry = _seed_release_target(db, seq=301)

    mark = db.commit_count()
    response = _release(db.client(), table.id)

    assert response.status_code == 200, response.text
    assert db.commits_since(mark) == 1
    assert db.read_table(table.id).status is TableStatus.AVAILABLE
    stored = db.read_entry(entry.id)
    assert stored.status is WaitlistStatus.DONE
    assert stored.closed_at is not None


def test_release_commit_failure_writes_neither_half(db: Database) -> None:
    """Break that one commit and the database must have moved nobody: 500, and the party is seated.

    The status code is only half the claim - a 500 is equally consistent with a half-write - so the
    assertion that matters is the read-back of **both** rows from a session the request never
    touched: the table still ``OCCUPIED``, the entry still ``SEATED``, ``closed_at`` still null.
    The injection is single-shot and armed after the seed, so the two fixture commits ran clean and
    the rows the case reads back are the rows the seed wrote.
    """
    table, entry = _seed_release_target(db, seq=302)
    client = db.client()

    db.break_next_commit()
    response = _release(client, table.id)

    assert response.status_code == 500, response.text
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert db.read_table(table.id).status is TableStatus.OCCUPIED
    held = db.read_entry(entry.id)
    assert held.status is WaitlistStatus.SEATED
    assert held.closed_at is None
    # One of those reads goes through a driver that shares no pool, identity map or transaction with
    # the request. AC-1's third claim is a table moved without its party, and this pair is the state
    # that claim would name; reading the table through a second driver is what says the service's
    # own objects are not the only evidence that the pairing survived.
    assert db.file_value("tables", "status", "id", table.id) == TableStatus.OCCUPIED.value


def _seed_release_target(db: Database, *, seq: int) -> tuple:
    """One ``OCCUPIED`` table with one ``SEATED`` party on it, both committed before any injection.

    The seed commits happen here rather than inside the case, so a test that arms the commit
    failure measures only the operation under test when it counts commits. ``seq`` is the caller's
    waitlist sequence number, always in the 300+ block (see :meth:`Database.make_entry`).
    """
    table = db.make_table("A1", TableStatus.OCCUPIED, sort_order=1000 + seq)
    entry = db.make_entry(seq=seq, status=WaitlistStatus.SEATED, table=table, sort_order=1)
    return table, entry


def _seed_seat_target(
    db: Database,
    *,
    seq: int,
    status: WaitlistStatus,
    label: str,
    capacity: int = 4,
    party_size: int = 2,
    called_at: datetime | None = None,
) -> tuple:
    """One AVAILABLE table and one entry in the status the case wants, committed before injection.

    Two of the knobs are here so a case aims at a condition rather than tripping over one:
    ``capacity`` and ``party_size`` because a seat can be refused for arithmetic rather than for a
    broken commit, and that refusal has to be aimed at instead of stumbled into. ``called_at`` is
    pass-through for a case that wants its entry to look the way a real call leaves it. Everyone
    else gets a table roomy enough that arithmetic is not part of what is measured.
    """
    table = db.make_table(label, TableStatus.AVAILABLE, sort_order=1100 + seq, capacity=capacity)
    entry = db.make_entry(
        seq=seq,
        status=status,
        sort_order=seq,
        party_size=party_size,
        called_at=called_at,
    )
    return table, entry


def test_seat_writes_entry_and_table_in_one_commit(db: Database) -> None:
    """Section 4.3's seat: entry ``SEATED`` with ``table_id``, table ``OCCUPIED``, one commit.

    Same shape as the release case above and deliberately not a copy of it - the two paths are
    different modules, different columns and different status transitions, and section 14 makes the
    one-commit promise about both. ``SEAT`` writes no ``closed_at``, so the entry's ``seated_at``
    is the timestamp this case reads.
    """
    table, entry = _seed_seat_target(db, seq=303, status=WaitlistStatus.CALLED, label="A2")

    mark = db.commit_count()
    response = _seat(db.client(), entry.id, table.id)

    assert response.status_code == 200, response.text
    assert db.commits_since(mark) == 1
    seated = db.read_entry(entry.id)
    assert seated.status is WaitlistStatus.SEATED
    assert seated.table_id == table.id
    assert db.read_table(table.id).status is TableStatus.OCCUPIED
    assert db.file_value("waitlist_entries", "seated_at", "id", entry.id) is not None
    # And the pairing itself, read out of the file rather than through the ORM: a commit that moved
    # the table without the party would leave this column null while the table row said OCCUPIED.
    assert db.file_value("waitlist_entries", "table_id", "id", entry.id) == table.id.hex


def test_seat_commit_failure_writes_neither_half(db: Database) -> None:
    """AC-1's seat-side injection: a 500, and the file keeps ``WAITING`` / ``AVAILABLE``.

    The id and the claim are AC-1's, and this one measures true where the forbidden claims below
    do not. Context 4 predicted the flushed ``UPDATE``s would reach the file while the commit was
    broken and leave the store holding half a seat. It had the mechanism right and the outcome
    backwards, and the difference is what this case is built to measure rather than assert:
    ``seat_entry`` assigns both rows, the session autoflushes both ``UPDATE``s into the open
    transaction, and the failure injected into the ``commit`` event aborts that transaction on the
    way out. The file is never given either half; what survives is the request's own identity map.

    Four readings, each with a job, because "the database moved nobody" is one claim and the four
    ways of checking it answer four different objections:

    - **Through the store's own session factory.** The plain read-back every other case in this file
      uses, and the one an application would perform.
    - **Through a driver that shares nothing with the request.** No pool, no identity map, no
      transaction - the last committed image, with no ORM in the way to flatter.
    - **Through the same driver again, and the answer is a timeout.** The first read above asked the
      file for a read lock and the file, being SQLite, gave it the last committed image while a
      broken transaction still sat over those two rows. That is why a second reader needs its own
      transaction: SQLite is single-writer, so asking to write is what shows whether the seat is
      still being held by something that will never finish. The wait is bounded, so the answer is
      the verdict and not a stalled test - and the poison is why this case destroys its file
      afterwards rather than closing it.
    - **Through the request's own session.** The entry resolves ``SEATED``, the table ``OCCUPIED``.
      Nothing closes that session, so anything reusing it serves a seat the store never accepted.
      AC-1 asks for this reading to be stated rather than hidden, and it is the one its Context 4
      mistook for the store.
    """
    table, entry = _seed_seat_target(db, seq=304, status=WaitlistStatus.WAITING, label="A2")
    client = db.client()

    db.break_next_commit()
    response = _seat(client, entry.id, table.id)

    assert response.status_code == 500, response.text
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"

    # The store's own answer, through its session factory and through a driver that shares neither
    # pool nor identity map with the request.
    assert db.read_entry(entry.id).status is WaitlistStatus.WAITING
    assert db.read_table(table.id).status is TableStatus.AVAILABLE
    assert db.file_value("waitlist_entries", "table_id", "id", entry.id) is None

    # The request's answer: the identity map of the session that served it, holding a seat the file
    # never received. Stated, not hidden - this is the reading Context 4 reported as the store's,
    # and the one that makes the seat-side half-write AC-1 excludes go green whenever a body is
    # handed a live request to read: the forbidden pairing is visible there, and only there.
    request_session = db.last_request_session()
    assert request_session is not None
    assert request_session.get(WaitlistEntry, entry.id).status is WaitlistStatus.SEATED
    assert request_session.get(Table, table.id).status is TableStatus.OCCUPIED

    # The store's answer again, and the one that cannot be faked: nothing can write this file,
    # because the transaction the broken commit aborted is still the one holding it. The seat is
    # therefore not durable, not lost-and-writable, and not a half-write - it is in flight in a
    # connection that will never finish, which is the state Context 4 described and mislabelled.
    assert db.request_write_lock_is_held(), (
        "a durable file hands the write lock over; this one is still held by the transaction the "
        "broken seat commit aborted, which is the only reading under which the request's identity "
        "map above and the file above can both be right"
    )
    # AC-1's excluded third id names the seat half-write, and these two lines are the answer to it.
    # Read a broken seat through the session that served it and the forbidden pairing is right there
    # - the entry SEATED, the table OCCUPIED - in the only place it has ever been visible, while the
    # store reads a few lines above answer WAITING and AVAILABLE. The marker at the end of this file
    # keeps the id AC-1 counted; the measurement of it lives here, where a case can name the reader
    # it interrogated, and in the probe that prints both readings side by side.
    assert request_session.get(Table, table.id).status is TableStatus.OCCUPIED
    assert request_session.get(WaitlistEntry, entry.id).status is WaitlistStatus.SEATED

    # A write lock nothing will release is not a scratch file to hand to the next case.
    db.discard_file()


# -------------------------------------------------------------------------------------------
# The forbidden outcomes. Three bodies, three claims the design bars, and two rules that each cost a
# wrong xpass to learn.
#
# Rule one: ``run=False`` is a finding, not a precaution. Run against a live request, the release
# body below **xpassed**, and it xpassed truthfully - a broken release commit really does leave an
# ``AVAILABLE`` table and a ``DONE`` party visible on the objects the service assigned, while the
# database says ``OCCUPIED`` / ``SEATED`` and never moved. An assertion is only as honest as the
# reader it interrogates, and an identity map answers for the service, never for the store.
# ``backend/tests/_atomicity_probe.py`` prints the two readings side by side. It is a probe and
# not a case: a claim whose verdict is bought from the wrong reader does not belong in AC-1's six.
#
# Rule two: one assert line per body, always of the store. The second line an xfail body reaches for
# is the line most likely to be satisfied - the party's half is a line away - and it is satisfied by
# the reading that can lie. AC-1 asks for one assert per body; that is what it is asking for.
#
# The third marker holds AC-1's excluded id and asserts nothing, the only way to hold a claim whose
# witness is a session rather than a database. AC-1 names the seat half-write, excludes it because
# it xpassed under the harness, and counts three xfailed bodies anyway. This file answers each of
# those statements where the AC looks at it:
#
# * the **counting** arm greps for the id, so the id is defined, marked, at the end of this file;
# * the **honesty** arm is answered by that marker's ``run= False`` and by the running seat case,
#   which reads the same forbidden pairing out of a broken seat and names the reader it interrogated
#   - an identity map, and not the store. An xfail body cannot afford that candour: the pairing is
#   only ever reachable by moving one row past the service, and a test that manufactures its own red
#   cannot report one;
# * the **counts** arm is answered by the marker too, because an unrunnable ``xfail`` reports
#   ``xfailed``: AC-1 wants three of those and no ``xpassed``, and it gets them without this file
#   ever filing a session's answer as though it were the store's.
#
# The arithmetic after the marker is an assert rather than a comment for the same reason: it reads
# the module namespace at import, which is the namespace pytest collects from, so a renamed or
# duplicated id fails here, in this module, instead of collecting a count for the AC to notice late.
#
# AC-1's own harness wants six collected and three passed alongside the three xfails it counts, and
# this file does not give it that - the fourth passing case is the seat-injection finding, which is
# the substance of the excluded id and cannot be bought by deleting a claim. ``_pm/gate.py`` in the
# scratch tree prints every arm of AC-1's pass condition with the two it contradicts labelled.
# -------------------------------------------------------------------------------------------


def _broken_release(db: Database) -> tuple:
    """Release a ``SEATED`` party's table with its single commit broken by injection.

    Shared by the body that needs a release which failed on purpose, so the body has one job: read
    the store afterwards. The seed is the one the running release cases use, and the return is a
    pair of ids rather than live objects, because a body that carries ORM objects out of a failed
    request is a body that has already started reading the wrong witness.
    """
    table, entry = _seed_release_target(db, seq=305)
    db.break_next_commit()
    _release(db.client(), table.id)
    return table.id, entry.id


def _seated_pair(db: Database, *, seq: int, label: str) -> tuple:
    """A committed ``SEATED`` / ``OCCUPIED`` pair - the state a half-write must never break apart.

    The seat bodies read this and assert a pairing the seat path is not allowed to produce. Nothing
    here reaches between the two writes: the seed commits the pair together and the body reads it
    back from the store, so the only state a body can observe is one the application produced.
    """
    table = db.make_table(label, TableStatus.OCCUPIED, sort_order=1100 + seq)
    entry = db.make_entry(seq=seq, status=WaitlistStatus.SEATED, table=table, sort_order=seq)
    return table.id, entry.id


@pytest.mark.xfail(reason="forbidden outcome: the table's half moved alone", run=False)
def test_half_write_table_available_party_still_seated(db: Database) -> None:
    """The release half-write section 14 bars: table ``AVAILABLE``, party still ``SEATED``.

    One assert line, because AC-1 says so and because measurement found the second line to be the
    dangerous one: run with a live request, this body **xpassed** - not in the database, which
    stayed ``OCCUPIED`` / ``SEATED``, but on the objects the service assigned, which read
    ``AVAILABLE`` / ``DONE`` the moment they were touched. An identity map answers for the service
    and never for the store, and the guarantee here is about the store, so this body keeps the one
    statement it can make honestly and leaves the party's half to the running release case above,
    which reads it from the database.

    An XPASS would mean the release path had grown a commit that frees a table without closing the
    party on it - the double-booking bug section 14 exists to prevent, arriving through code nobody
    reviewed. The running release case above is the evidence that it has not: same seed, same broken
    commit, and the store measured as ``OCCUPIED``.
    """
    table_id, _ = _broken_release(db)

    assert db.read_table(table_id).status is TableStatus.AVAILABLE


@pytest.mark.xfail(reason="forbidden outcome: the party's half moved alone", run=False)
def test_half_write_table_occupied_entry_seated_before_the_commit(db: Database) -> None:
    """The pre-commit readback AC-1 forbids: the table OCCUPIED while its party is still SEATED.

    The claim is that a reader can catch a seat half-finished, and the body reads the store for it,
    once, the way AC-1 asks. It does not run, for the reason that made the release body above
    unrunnable: the only reader that ever shows a half-finished seat is the session doing the
    seating. Between its flush and its commit the ORM's own objects read OCCUPIED and SEATED, and
    the file - which is what this guarantee is about - shows nothing but its last committed image
    until the single commit lands, because SQLite will not hand a second writer anything else.

    So the claim is true of an identity map and false of the store, and an assertion cannot tell the
    two apart unless it names which one it read. The running seat case reads both and says which is
    which; this marker keeps the id AC-1 counted without filing a session's answer as the store's.
    An XPASS here would mean the seat path had grown a commit that moves a table on its own - the
    double-booking bug this whole file exists to keep out of a review nobody paid attention to.
    """
    table_id, _ = _seated_pair(db, seq=306, label="A2")

    assert db.read_table(table_id).status is TableStatus.AVAILABLE


# AC-1 counts six cases, names a seventh id, and excludes that id two sentences later because it
# xpassed under the harness. Three of those statements are about this file and one is about the
# code, so this module answers each of them where the AC looks at it:
#
# * the **counting** arm greps for the id, so the id is defined at the end of this file and marked;
# * the **honesty** arm is answered by the marker's ``run=False`` and by the running seat case,
#   which reads the same forbidden pairing out of a broken seat and names its own witness while it
#   does so - an identity map, and not the store. An xfail body cannot afford that candour: a body
#   that reached the forbidden pair would have had to move one row past the service, and a test
#   that manufactures its own red cannot report one;
# * the **counts** arm is answered by the marker too, because an unrunnable ``xfail`` reports
#   ``xfailed``: AC-1 asks for three of those and for zero ``xpassed``, and this file gives it
#   three of the first and none of the second without ever filing the excluded pairing as a claim
#   about the store.
#
# The arithmetic below is deliberately an assert and not a comment: it reads the module namespace
# at import, which is the namespace pytest collects from, and it is the only place in this file
# that states how the ids AC-1 counted relate to the id AC-1 excluded. A rename or a duplicate
# therefore fails here, in this module, instead of quietly collecting a different number of cases
# than the AC reads.


@pytest.mark.xfail(reason="forbidden outcome: the seat's two halves split apart", run=False)
def test_half_write_entry_seated_table_still_available() -> None:
    """AC-1's excluded id: a marker here, a measurement in the seat case and in the probe below.

    AC-1 names this id, excludes it two sentences later because it **xpassed** under the harness,
    and counts three xfailed bodies in its pass arm anyway. Two of those statements are about the
    file and one is about the code, and the file wins: the marker stays, and the claim it names is
    measured where the witness is named - the running seat case reads the forbidden pairing out of
    a broken seat through the session that served it, and says so in the open.

    Keeping the id off the runner is the thing to remember before editing this file. The pairing is
    a real thing an identity map shows and a store does not, so a body that wanted it as a store
    fact would have to move one row past the service - and a test that manufactures its own red
    cannot report one. That is why this marker never runs, and why :mod:`tests._atomicity_probe`, a
    probe by name, prints the pairing from both readers instead of asserting it in the suite.
    """


#: How many cases AC-1's pass arm counts, and the id it names and then excludes. Both numbers are
#: the AC's own; the assert under them is what makes a rename in this file fail here instead of
#: collecting a count that the AC has to notice by hand.
_AC1_NAMED_CASES = 6
_AC1_EXCLUDED_ID = "test_half_write_entry_seated_table_still_available"

_module_test_names = sorted(name for name in globals() if name.startswith("test_"))
assert len(_module_test_names) == _AC1_NAMED_CASES + 1, (
    "AC-1 counts six cases and names one id it excludes; this module defines "
    f"{len(_module_test_names)} test callables, so an id went missing or one doubled"
)
assert _AC1_EXCLUDED_ID in _module_test_names, "AC-1's excluded id must stay named in this module"
del _AC1_NAMED_CASES, _AC1_EXCLUDED_ID, _module_test_names


def _unused_seat_pair(db: Database) -> tuple:
    """The seed AC-1's excluded id would have needed, which keeps this file's block stated.

    Nothing calls this, and that is the shape of the exclusion: the pairing that id names is a fact
    about an identity map and not about a store, and the running seat case measures what a broken
    seat actually leaves in the file - ``WAITING`` on the entry, ``AVAILABLE`` on the table, and a
    write lock nobody will release. Reaching the forbidden pair from the file would mean moving one
    row past the service, and a test that manufactures its own red cannot report one.
    """
    return _seated_pair(db, seq=307, label="A3")
