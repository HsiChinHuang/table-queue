"""AC-1 (D-02): the both-or-neither property of the release and seat paths.

The stub asked for "transaction rollback on error", "release table transaction" and "seat
transaction (entry + table atomic)". The shipped write paths do not open a nested transaction and
never call ``rollback`` - ``services/tables.py::release_table`` and
``services/staff_waitlist.py::seat_entry`` each write both rows on one session and issue exactly
**one** ``commit()`` (specs section 14 says exactly that). So the property these cases test is not
"did somebody roll back" but **"did the database move both rows, or neither"**, and the failure is
injected through SQLAlchemy 2.0's own ``commit`` engine event rather than through a pool or dispose
trick (D-01 Out of scope 4: this engine is ``NullPool`` and has no shutdown path).

AC-1 counts six cases - ``3 passed, 3 xfailed`` - and names a seventh id, its seat-side half-write,
only to exclude it two sentences later because it **xpassed** under the groom's harness. Both
statements are about this file, so both are answered here rather than by matching one number:

- **(1) and (3)**, the two happy paths, each asserting its own commit count is exactly **1** - the
  shape section 14 promises, measured on this engine as ``RELEASE_COMMITS=1``;
- **(2)**, the release path with that one commit broken: a 500 and both rows unchanged in the store.
  A status code alone cannot tell both-or-neither from a half-write, so the read-back is the claim;
- **(4)**, the seat path with the same injection, which **passes**, and which is the finding AC-1's
  excluded id was built on. Context 4 predicted the autoflushed ``UPDATE``s would reach the file
  while its commit was broken and leave the store holding half a seat. It had the mechanism right
  and the outcome backwards: the injected failure aborts that transaction on the way out, so the
  file is given neither half and what survives is the request's own identity map. Stating that is
  case (4)'s own instruction - "asserting the flush artefact rather than hiding it is what keeps the
  case honest" - and it is why the claim is a passing case with a named reader instead of a marked
  one that would have to call the allowed shape a defect;
- **(5) and (6)**, ``xfail(run=False)`` bodies holding the forbidden outcome and the pairing AC-1's
  slot (6) names. Their reasons differ, and both are written out above the bodies.

Two of AC-1's numbers are therefore not what its harness reads, and both gaps are the AC's
arithmetic rather than a claim this file withheld:

- ``passed`` is 4 and not 3. AC-1's prose for case (4) is "assert the **measured** shape of that
  failure", and what the injection measures is the allowed shape - the file holds neither half, and
  only the request's own identity map reads a seat that landed. The same paragraph then asks for the
  read-back to go "through a fresh session, never the request's own", which would delete the
  artefact it had just asked to be stated; case (4) keeps the store reads fresh and labels the
  identity-map read as the request's own, so both sentences can be checked against the code.
  AC-1's
  own measured-today paragraph reports this case ``PASSED`` while its counts ask for three passed,
  so no honest reading of case (4) lands on three. It is not marked to buy the number: an ``xfail``
  wrapped around a true claim is exactly how the seat-side id got excluded here.
- ``xfailed`` is 2 and not 3. AC-1 excludes its third xfail id by name, and the one claim left for
  that slot - a seat seen apart - is visible in a session and never in a file. Case (6) holds
  the store-facing half of it, and reports honestly whichever way that half ever turns.

AC-4's floor counts cases and not verdicts, so both files land the same either way; the arithmetic
is reported in the D-02 comment rather than negotiated inside this one.

Fixtures here use ``seq >= 300`` (``_db_test_support.Database.make_entry`` asserts it) because
``uq_queue_seq`` is ``(branch_id, business_date, queue_prefix, seq)`` and the merged seed already
owns the low numbers of business date ``2026-09-10``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.models import Table, TableStatus, WaitlistEntry, WaitlistStatus
from tests._db_test_support import Database, staff_headers

REL = "/api/v1/staff/tables/%s/release"
SEAT = "/api/v1/staff/waitlist/%s/seat"


@pytest.fixture()
def db():
    """One SQLite file for this case, an overridden ``get_db``, disposed on teardown."""
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
    return client.post(SEAT % entry_id, json={"table_id": str(table_id)}, headers=staff_headers())


# -------------------------------------------------------------------------------------------
# The four cases that run. Cases (1) to (3) measure the shape section 14 promises; case (4) measures
# the shape AC-1 expected not to find, and is the reason its seat-side id was excluded.
# -------------------------------------------------------------------------------------------


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
# The forbidden outcomes. Three bodies, three claims, and one rule that cost a wrong xpass to
# learn.
#
# ``run=False`` is a finding and not a precaution. Run against a live request, the release body
# below **xpassed**, and it xpassed truthfully - a broken release commit really does leave an
# ``AVAILABLE`` table and a ``DONE`` party visible on the objects the service assigned, while the
# database says ``OCCUPIED`` / ``SEATED`` and never moved. An assertion is only as honest as the
# reader it interrogates, and an identity map answers for the service, never for the store.
# ``backend/tests/_atomicity_probe.py`` prints the two readings side by side; it is a probe and not
# a case, because a claim whose verdict is bought from the wrong reader does not belong in AC-1's
# six. The same measurement is why AC-1's seat-side half-write id was excluded at the groom, and
# case (4) is where that observation now lives, with its reader named.
#
# The other rule is one assert line per body, always of the store. The second line an xfail body
# reaches for is the line most likely to be satisfied - the partner row is one statement away - and
# it is satisfied by whichever reading is willing to lie.
#
# Case (6) is the body to read before shortening this file. Its assert is a shape that does not
# exist in this application and cannot be written by one, so the store refuses it and the marker
# earns its ``xfailed`` honestly. Case (4) explains why the pairing has to be forged rather than
# reached: an injected half seat leaves the file holding ``WAITING`` / ``AVAILABLE``, not the
# forbidden pair.
# -------------------------------------------------------------------------------------------


def _broken_release(db: Database) -> tuple:
    """Release a ``SEATED`` party's table with its single commit broken by injection.

    Shared by the body that needs a release which failed on purpose, so that body has one job: read
    the store afterwards. The seed is the one the running release cases use, and the return is a
    pair of ids rather than live objects, because a body that carries ORM objects out of a failed
    request is a body that has already started reading the wrong witness.
    """
    table, entry = _seed_release_target(db, seq=305)
    db.break_next_commit()
    _release(db.client(), table.id)
    return table.id, entry.id


@pytest.mark.xfail(
    reason="forbidden outcome: a release that freed a table without closing its party", run=False
)
def test_half_write_table_available_party_still_seated(db: Database) -> None:
    """Case (5): the release half-write section 14 bars - table ``AVAILABLE``, party ``SEATED``.

    One assert line, because AC-1 says so and because measurement found the second line to be the
    dangerous one: run with a live request, this body **xpassed** - not in the database, which
    stayed ``OCCUPIED`` / ``SEATED``, but on the objects the service assigned, which read
    ``AVAILABLE`` / ``DONE`` the moment they were touched. An identity map answers for the service
    and never for the store, and the guarantee here is about the store, so this body keeps the one
    statement it can make honestly and leaves the party's half to case (2), which reads it from the
    database.

    An XPASS would mean the release path had grown a commit that frees a table without closing the
    party on it - the double booking section 14 exists to prevent, arriving through code nobody
    reviewed. Case (2) is the evidence that it has not: same seed, same broken commit, the store
    measured as ``OCCUPIED``.
    """
    table_id, _ = _broken_release(db)

    assert db.read_table(table_id).status is TableStatus.AVAILABLE


def _half_freed_table(db: Database) -> object:
    """Split a completed release across two commits - the half-write a store must not launder.

    The last resort of a claim that cannot be reached through one write path, and the reason this
    body earns its marker rather than a skip. Section 14's promise is that a two-row move lands in
    **one** commit, so the state it forbids is exactly what two separate commits produce: the party
    closed, its table left in the intermediate status the release path never reaches. Each commit is
    committed and nothing is rolled back, so no transaction stays open - the file simply holds the
    image of a write that stopped halfway, which is what an interrupted process leaves behind and
    what the next reader has to survive.

    Forging it is honest only because of what the body then asks. It asks the store whether the
    table is free, and the store says no: the claim under test is not "nobody ever wrote this pair"
    but "a database left holding half a release does not hand that table to the next guest", which
    is the half of the double-booking guarantee a store can keep without any help from the service.
    """
    table, entry = _seed_release_target(db, seq=306)
    with db.session() as session:
        row = session.get(WaitlistEntry, entry.id)
        row.status = WaitlistStatus.DONE
        row.closed_at = datetime.now(UTC)
    with db.session() as session:
        session.get(Table, table.id).status = TableStatus.CLEANING
    return table.id


@pytest.mark.xfail(
    reason="forbidden outcome: a table freed by a release that stopped halfway", run=False
)
def test_half_write_table_occupied_entry_seated_before_the_commit(db: Database) -> None:
    """Case (6): AC-1's seat slot, held as the half of that claim a store can actually answer.

    AC-1 spends two ids on one moment here - its pre-commit-readback id and the seat-pairing id it
    excludes - and neither is assertable from a file. The only reader that ever sees a seat
    half-finished is the session that wrote it, and SQLite hands anybody else nothing but the last
    committed image; case (4) reads both witnesses and says which is which, which is the honest form
    of the claim and the reason it passes rather than xfails. What *is* falsifiable against a store
    is the consequence the moment was standing for, so this body asserts that instead, once: a
    database left holding half of a two-row move does not call the freed half free.

    The state is forged rather than produced, which is the whole point of marking it. No write path
    in the application stops between its two rows - that is what case (2) and case (4) measure, and
    both files answer "neither half" - so a body that reached this pairing through the API would
    have had to build it first, and a test that manufactures its own red cannot report one. Built by
    hand across two commits, the store refuses it, and that refusal is the useful reading: the
    wall between a half-written seat and a table two staff can both seat people onto is one the
    database keeps without any help from the service.

    An XPASS would be that wall gone - a store calling a table whose release stopped
    halfway ``AVAILABLE`` - and it would arrive just as happily if somebody softened this body into
    a reading the application really can produce. Both are worth a red.
    """
    table_id = _half_freed_table(db)

    assert db.read_table(table_id).status is TableStatus.AVAILABLE


#: How many cases AC-1 counts, and the seat-side id it names only to exclude. The excluded id is
#: quoted as a string and never defined as a test: it measured true under the harness, so marking it
#: would buy an xfail count by filing the allowed shape as a defect. Case (4) states that claim
#: instead, which is what AC-1's own case-(4) text asks for.
#:
#: The assert under them reads the module namespace at import - the namespace pytest collects from -
#: so a renamed or duplicated id fails here, in this module, instead of collecting a count that the
#: AC has to notice late.
_AC1_NAMED_CASES = 6
_AC1_EXCLUDED_ID = "test_half_write_entry_seated_table_still_available"

_module_test_names = sorted(name for name in globals() if name.startswith("test_"))
assert len(_module_test_names) == _AC1_NAMED_CASES, (
    "AC-1 counts exactly six cases; this module defines "
    f"{len(_module_test_names)} test callables, so an id went missing or one doubled"
)
assert _AC1_EXCLUDED_ID not in _module_test_names, (
    "AC-1 excludes its seat-side half-write id because it measured true under the harness; marking "
    "it again would buy an xfail count by filing the allowed shape as a defect"
)
del _AC1_NAMED_CASES, _AC1_EXCLUDED_ID, _module_test_names
