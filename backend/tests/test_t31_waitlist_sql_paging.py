"""Staff waitlist list paginates in SQL instead of materialising the full result (t31 / #86).

Regression tests for the audit finding B-2: the list path used to fetch the day's whole
filtered set and slice it in Python, and answered ``limit=0`` with 200 empty items and a
non-zero total. The six behaviours the AC set pins:

- AC-1 - ``limit`` is ``ge=1`` (a zero page is meaningless for a list endpoint) and ``offset``
  stays ``ge=0``; ``limit=0`` and the negative arms are 422, ``limit=1`` answers one item.
- AC-2 - with a 200-row fixture the page is the SQL slice of the full ordered list: the first
  page is the full list's prefix, the tail page is its tail, an offset past the end answers an
  empty page, and queue order holds within every page.
- AC-3 - ``total`` is the filter size from a COUNT, identical for every page, and the
  ``party_size`` filter narrows it.
- AC-4 - the no-search page SELECT carries ``LIMIT``/``OFFSET`` with the requested bounds and a
  ``COUNT`` statement runs over the same filter, verified by capturing executed SQL on the
  engine rather than by timing.
- AC-5 - the body is exactly ``{items, total}`` with the ``WaitlistEntryResponse`` fields, and
  the reorder still receives the *full* active set (R-B07-1).
- AC-6 - ``search`` composes with paging: ``total`` counts the matches and the offset applies to
  the filtered set.

Ownership follows the shipped discipline in ``test_t29_int_bounds.py``: this module owns its
scratch store through ``tests._db_test_support.Database`` and closes it on teardown.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event

from app.models import WaitlistStatus
from tests._db_test_support import (
    Database,
    staff_headers,
)

WAITLIST = "/api/v1/staff/waitlist"
REORDER = f"{WAITLIST}/reorder"
FIXTURE_ROWS = 200
"""The AC-2/AC-3/AC-6 fixture size: big enough that a full-fetch-then-slice is a different
behaviour from a bounded SELECT, small enough that the suite stays fast."""

ENTRY_FIELDS = (
    "id",
    "queue_number",
    "full_queue_number",
    "status",
    "party_size",
    "created_at",
    "updated_at",
    "name",
    "phone_masked",
    "note",
    "source",
    "cancelled_reason",
    "called_at",
    "seated_at",
    "remaining_seconds",
    "hold_minutes_snapshot",
    "table_id",
    "table_label",
)


@pytest.fixture()
def store():
    """A scratch store with the seeded branch and the 200-row fixture on the queue day."""
    database = Database("t31_paging")
    database.seed_branch()
    _seed_fixture(database)
    try:
        yield database
    finally:
        database.close()


@pytest.fixture()
def client(store):
    """A client whose ``get_db`` resolves to this module's scratch store."""
    return store.client()


def _seed_fixture(database: Database) -> None:
    """Write the 200-row WAITING fixture plus a few small-party rows the filter arms need.

    Every row sits on the store's queue day with a distinct ``sort_order``, so the queue order
    is the fixture's insertion order and the ground truth is computable in Python.
    """
    for i in range(FIXTURE_ROWS):
        database.make_entry(
            seq=300 + i,
            status=WaitlistStatus.WAITING,
            name=f"Fix{i:03d}",
            party_size=2,
        )
    # A handful of party_size=1 rows so the party_size filter's total is strictly between 0 and
    # the unfiltered total rather than equal to it.
    for i in range(4):
        database.make_entry(
            seq=600 + i,
            status=WaitlistStatus.WAITING,
            name=f"Small{i:02d}",
            party_size=1,
        )


def _ids(body: dict) -> list[str]:
    """The item ids of one list body, in page order."""
    return [item["id"] for item in body["items"]]


# --- AC-1: limit is ge=1, offset is ge=0, no upper bound ----------------------


def test_limit_zero_is_422_naming_field(store, client):
    """A zero page is meaningless for a list endpoint: 422 naming limit, not 200-empty."""
    res = client.get(f"{WAITLIST}?limit=0", headers=staff_headers())
    assert res.status_code == 422, res.text
    assert "limit" in res.text, res.text


def test_negative_limit_and_offset_still_422(store, client):
    """t29's negative-bound rejection survives the ge=1 refinement."""
    for query in ("limit=-1", "offset=-5"):
        res = client.get(f"{WAITLIST}?{query}", headers=staff_headers())
        assert res.status_code == 422, (query, res.text)


def test_limit_one_returns_exactly_one_item(store, client):
    """limit=1 answers 200 with one item and the full total."""
    res = client.get(f"{WAITLIST}?limit=1", headers=staff_headers())
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["items"]) == 1
    assert body["total"] == FIXTURE_ROWS + 4


# --- AC-2: the page is the SQL slice of the ordered list ----------------------


def test_first_page_is_full_list_prefix(store, client):
    """limit=10&offset=0 has exactly the first 10 ids of the full ordered list."""
    full = client.get(f"{WAITLIST}?limit=1000", headers=staff_headers()).json()
    assert full["total"] >= FIXTURE_ROWS
    page = client.get(f"{WAITLIST}?limit=10&offset=0", headers=staff_headers()).json()
    assert _ids(page) == _ids(full)[:10]


def test_tail_page_is_full_list_tail(store, client):
    """offset=total-3 has exactly the last 3 ids of the full ordered list."""
    full = client.get(f"{WAITLIST}?limit=1000", headers=staff_headers()).json()
    total = full["total"]
    page = client.get(f"{WAITLIST}?limit=10&offset={total - 3}", headers=staff_headers()).json()
    assert _ids(page) == _ids(full)[-3:]
    assert len(page["items"]) == 3


def test_offset_past_end_is_empty_page_with_unchanged_total(store, client):
    """offset=total answers 200 with items: [] and the same total."""
    full = client.get(f"{WAITLIST}?limit=1000", headers=staff_headers()).json()
    page = client.get(f"{WAITLIST}?limit=10&offset={full['total']}", headers=staff_headers()).json()
    assert page["items"] == []
    assert page["total"] == full["total"]


def test_queue_order_holds_within_pages(store, client):
    """sort_order then created_at (here: the fixture's insertion order) holds in every page."""
    full = client.get(f"{WAITLIST}?limit=1000", headers=staff_headers()).json()
    full_numbers = [item["queue_number"] for item in full["items"]]
    assert full_numbers == sorted(full_numbers)
    for offset in (0, 50, 190):
        page = client.get(
            f"{WAITLIST}?limit=10&offset={offset}", headers=staff_headers()
        ).json()
        numbers = [item["queue_number"] for item in page["items"]]
        assert numbers == sorted(numbers), (offset, numbers)
        assert numbers == full_numbers[offset : offset + 10]


# --- AC-3: total is the filter size, from COUNT, independent of paging --------


def test_total_is_stable_across_paging(store, client):
    """The same filter answers the same total for every page, including past the end."""
    totals = [
        client.get(f"{WAITLIST}?{query}", headers=staff_headers()).json()["total"]
        for query in (
            "limit=1&offset=0",
            "limit=50&offset=100",
            "limit=1&offset=500",
        )
    ]
    assert totals[0] == totals[1] == totals[2], totals
    assert totals[0] == FIXTURE_ROWS + 4


def test_all_total_is_at_least_active_total(store, client):
    """status=ALL counts a superset of the default ACTIVE group."""
    active = client.get(WAITLIST, headers=staff_headers()).json()["total"]
    all_total = client.get(f"{WAITLIST}?status=ALL", headers=staff_headers()).json()["total"]
    assert all_total >= active


def test_party_size_filter_narrows_total(store, client):
    """party_size=2 counts only the two-top fixture rows: between 0 and the unfiltered total."""
    unfiltered = client.get(WAITLIST, headers=staff_headers()).json()["total"]
    narrowed = client.get(f"{WAITLIST}?party_size=2", headers=staff_headers()).json()["total"]
    assert 0 < narrowed < unfiltered, (narrowed, unfiltered)
    assert narrowed == FIXTURE_ROWS


# --- AC-4: the page SELECT is bounded in SQL; total comes from COUNT ----------


def test_page_select_is_bounded_and_total_is_count(store, client):
    """limit=10&offset=20 issues a SELECT with LIMIT/OFFSET 10/20 and a COUNT, captured on the
    engine - the service no longer materialises the day to answer the page."""
    stmts: list[tuple[str, tuple]] = []

    def capture(conn, cursor, stmt, params, context, executemany):
        stmts.append((stmt, tuple(params) if params else ()))

    event.listen(store.engine, "after_cursor_execute", capture)
    try:
        res = client.get(f"{WAITLIST}?limit=10&offset=20", headers=staff_headers())
    finally:
        event.remove(store.engine, "after_cursor_execute", capture)
    assert res.status_code == 200, res.text
    assert len(res.json()["items"]) == 10

    upper = [(s.upper(), p) for s, p in stmts]
    assert any("COUNT" in s for s, _ in upper), [s for s, _ in upper]
    # The page SELECT is the bounded statement carrying the requested bounds. Other bounded
    # statements on the request (the token-generation probe, the queue-day .first() read) are
    # LIMIT 1 OFFSET 0 probes with no page bounds in their params.
    bounded = [(s, p) for s, p in upper if "LIMIT" in s and 10 in p and 20 in p]
    assert bounded, [s for s, _ in upper]
    stmt, params = bounded[0]
    assert "OFFSET" in stmt, stmt
    assert "WAITLIST_ENTRIES" in stmt, stmt


# --- AC-5: response shape unchanged; the full-set path stays intact -----------


def test_response_shape_is_items_total_with_entry_fields(store, client):
    """The list body is exactly {items, total} and each item carries the entry fields."""
    body = client.get(f"{WAITLIST}?limit=5", headers=staff_headers()).json()
    assert set(body.keys()) == {"items", "total"}
    assert len(body["items"]) == 5
    for key in ENTRY_FIELDS:
        assert key in body["items"][0], f"item field missing: {key}"


def test_reorder_still_receives_full_active_set(store, client):
    """A reorder naming every id of the full default list succeeds and returns that exact order
    (R-B07-1): paging the list must not have paged the reorder's domain."""
    full = client.get(f"{WAITLIST}?limit=1000", headers=staff_headers()).json()
    ordered = list(reversed(_ids(full)))
    res = client.post(REORDER, headers=staff_headers(), json={"ordered_ids": ordered})
    assert res.status_code == 200, res.text
    assert _ids(res.json()) == ordered


# --- AC-6: search and party_size compose with paging --------------------------


def test_search_total_counts_matches_and_pages_the_filtered_set(store, client):
    """search=Fix over the 200-row fixture: total 200, the page is a prefix of the filtered
    list, and offset applies to the filtered set."""
    first = client.get(f"{WAITLIST}?search=Fix&limit=10", headers=staff_headers()).json()
    assert first["total"] == FIXTURE_ROWS
    assert len(first["items"]) == 10
    assert all(item["name"].startswith("Fix") for item in first["items"])

    full = client.get(f"{WAITLIST}?search=Fix&limit=1000", headers=staff_headers()).json()
    assert full["total"] == FIXTURE_ROWS
    assert _ids(first) == _ids(full)[:10]

    tail = client.get(
        f"{WAITLIST}?search=Fix&limit=10&offset=195", headers=staff_headers()
    ).json()
    assert len(tail["items"]) == 5
    assert tail["total"] == FIXTURE_ROWS
    assert _ids(tail) == _ids(full)[-5:]
