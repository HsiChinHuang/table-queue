"""AC-3 (D-02): the reorder transaction - one commit for n positions, and both-or-neither.

``_docs/testing.md`` has named ``test_reorder_waitlist_success``,
``test_reorder_waitlist_missing_ids`` and ``test_reorder_waitlist_extra_ids`` since phase 1, and no
module ever collected them: what the
suite had were B-07's transport-shape tests, which put an id in a *path*, never a list in a *body*.
B-07 AC-13 measured reorder with an out-of-band probe that does not run with the suite. These four
cases are the operation's first in-suite coverage, and they are the same four arms the naming
document asks for - the success, the missing-id refusal, and the shape refusals.

Two rules of the operation shape what a case here has to do before it can assert anything:

- ``services/staff_waitlist.py::reorder`` (R-B07-1) refuses any ``ordered_ids`` list that is not
  **exactly** the current active set, so each case calls ``Database.clear_active_set()`` - one bulk
  ``DELETE FROM waitlist_entries`` - and then seeds the set it names. A per-row delete sweep was
  measured leaving rows behind (Context 5a), which shows up as a 409 whose ``expected`` list is
  longer than the ``received`` one;
- ``ordered_ids`` must be **strings** (``schemas.py:86-94``): UUID columns reject ints at
  statement-compile time with ``'int' object has no attribute 'hex'``, and the schema answers 422
  ``VALIDATION_ERROR`` before the service ever runs. That is the fourth case below.

Rows are seeded with ``seq >= 300`` and business date ``2026-09-10``, the same ``uq_queue_seq``
neighbourhood AC-1 stays out of.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.models import WaitlistStatus
from tests._db_test_support import Database, staff_headers

REORDER = "/api/v1/staff/waitlist/reorder"


@pytest.fixture()
def db():
    """This module's own SQLite file, cleared and re-seeded per case, disposed on teardown."""
    database = Database("d02_reorder")
    database.seed_branch()
    database.start_commit_listener()
    try:
        yield database
    finally:
        database.close()


def _reorder(client: TestClient, ordered_ids: list[object]) -> object:
    """POST a reorder whose body is exactly ``ordered_ids`` - the only field the schema declares."""
    return client.post(
        REORDER,
        json={"ordered_ids": [str(entry_id) for entry_id in ordered_ids]},
        headers=staff_headers(),
    )


def _active_set(db: Database, count: int, first_seq: int = 301) -> list:
    """Clear the active set, then write exactly ``count`` ``WAITING`` rows and return them.

    Clearing first is not hygiene for its own sake: R-B07-1 compares the submitted list against
    every ``WAITING`` + ``CALLED`` row the branch holds, so a leftover row from any other case makes
    the legal reorder below answer 409 rather than 200.
    """
    db.clear_active_set()
    return [db.make_entry(seq=first_seq + i, status=WaitlistStatus.WAITING) for i in range(count)]


def test_reorder_of_the_exact_active_set_lands_1_to_n_in_one_commit(db: Database) -> None:
    """specs 4.5 through the transport: the submitted order becomes ``sort_order`` 1..n.

    One commit carries the whole rewrite. Three rows are written in sequence order and submitted
    reversed, so a service that ignored the list would answer 200 and still leave the positions at
    their seed values - the positions are
    read back from a session the request never used rather than from the response body. The commit
    count is the other half of the case: reorder writes n rows and gets away with **one** engine
    commit, which is what makes "the queue moved all at once or not at all" observable at all.
    """
    rows = _active_set(db, 3)
    client = db.client()
    submitted = [rows[2], rows[1], rows[0]]

    mark = db.commit_count()
    response = _reorder(client, [row.id for row in submitted])

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 3
    assert [item["queue_number"] for item in payload["items"]] == [
        row.queue_number for row in submitted
    ]
    assert db.commits_since(mark) == 1
    for position, row in enumerate(submitted, start=1):
        stored = db.read_entry(row.id)
        assert stored is not None
        assert stored.sort_order == position, (row.queue_number, stored.sort_order)


def test_reorder_commit_failure_moves_nobody(db: Database) -> None:
    """Break reorder's one commit and no position moves - asserted from the rows, not the promise.

    This is the case whose name states what the **rows** do rather than what section 14 intends:
    ``reorder`` assigns ``sort_order`` one row at a time and commits once, so breaking that commit
    makes the answer a 500 while SQLAlchemy's flush has already written the *first* position inside
    the still-open transaction. The rollback undid it, and what this case asserts is the measured
    outcome - every position reads back at the value its seed gave it, none of them the value the
    refused request asked for. Asserting the read-back is the point; the 500 alone would also be
    consistent with a partial rewrite.
    """
    rows = _active_set(db, 3)
    client = db.client()
    seeded_positions = {row.id: row.sort_order for row in rows}
    submitted = [rows[2], rows[1], rows[0]]

    db.break_next_commit()
    response = _reorder(client, [row.id for row in submitted])

    assert response.status_code != 200, response.text
    assert response.status_code == 500, response.text
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    for row in rows:
        stored = db.read_entry(row.id)
        assert stored is not None
        assert stored.sort_order == seeded_positions[row.id], row.queue_number
        assert stored.sort_order != submitted.index(row) + 1


def test_reorder_with_a_missing_id_is_409_and_rewrites_nothing(db: Database) -> None:
    """R-B07-1: a list one row short is 409 ``CONFLICT``, and no position moves.

    The refusal is a conflict rather than a validation error because the request was well formed and
    the queue moved underneath the staff user - which is also why ``openapi.yaml`` declares no 409
    for this operation and the code reaches for section 11's general ``CONFLICT``. The 409 body's
    ``details`` pair (five expected against three received, measured) is what a client reconciles
    against, so the envelope is read as well as the status; the positions are then re-read to prove
    the refusal wrote nothing.
    """
    rows = _active_set(db, 3)
    client = db.client()
    seeded_positions = {row.id: row.sort_order for row in rows}

    response = _reorder(client, [rows[0].id, rows[1].id])

    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["code"] == "CONFLICT"
    assert sorted(error["details"]["expected"]) == sorted(str(row.id) for row in rows)
    assert error["details"]["received"] == sorted([str(rows[0].id), str(rows[1].id)])
    for row in rows:
        stored = db.read_entry(row.id)
        assert stored is not None and stored.sort_order == seeded_positions[row.id]


def test_reorder_with_a_non_uuid_id_is_422_and_rewrites_nothing(db: Database) -> None:
    """The fourth testing.md arm: a non-UUID member is 422 ``VALIDATION_ERROR``, never a 500.

    ``ReorderWaitlistRequest`` validates UUID-ability up front (``schemas.py:86-94``) precisely
    because handing a UUID column anything else fails later, at statement-compile time, with
    ``'int' object has no attribute 'hex'`` - a fixture-shaped crash reaching the wire as a 500. So
    the body here mixes two legitimate ids with one string the UUID parser refuses, and the answer
    must be the section 11 envelope's ``VALIDATION_ERROR`` at 422 with ``ordered_ids`` named.
    Nothing is rewritten: the set the seed wrote still reads in seed order.
    """
    rows = _active_set(db, 2)
    client = db.client()
    seeded_positions = {row.id: row.sort_order for row in rows}

    response = _reorder(client, [rows[0].id, "not-a-uuid", rows[1].id])

    assert response.status_code == 422, response.text
    payload = response.json()
    assert "detail" not in payload, payload
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert "ordered_ids" in str(payload["error"])
    for row in rows:
        stored = db.read_entry(row.id)
        assert stored is not None and stored.sort_order == seeded_positions[row.id]
