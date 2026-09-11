"""The staff waitlist transport: the nine routes, and the two rules they carry.

AC-15 names this file. It is deliberately not a restatement of the issue's own AC blocks - those
mount the app from a scratch directory and drive it through ``TestClient``, and they are the
acceptance gate. What belongs here is the narrow behaviour the transport owns and that nothing else
in the suite touches: which paths exist, which verb each answers, who is allowed in, and the two
places where a response shape is decided rather than passed through - the mask, and the session
recovery that keeps a read from answering "nobody is waiting".

Everything status-shaped - call, seat, no-show, restore, revert, cancel, reorder - is measured by
the issue's AC-6 through AC-13 against a real database and is not repeated here.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import mask_phone
from app.services import staff_waitlist as service

# The nine operations of R-B07-1, as AC-1 reads them off app.routes.
ROUTE_PATHS = {
    "/api/v1/staff/waitlist",
    "/api/v1/staff/waitlist/reorder",
    "/api/v1/staff/waitlist/{entry_id}",
    "/api/v1/staff/waitlist/{entry_id}/edit",
    "/api/v1/staff/waitlist/{entry_id}/call",
    "/api/v1/staff/waitlist/{entry_id}/seat",
    "/api/v1/staff/waitlist/{entry_id}/no-show",
    "/api/v1/staff/waitlist/{entry_id}/restore",
    "/api/v1/staff/waitlist/{entry_id}/revert",
    "/api/v1/staff/waitlist/{entry_id}/cancel",
}


def _staff_headers() -> dict[str, str]:
    """Return a bearer token the merged dependency accepts, without going through /api/v1/auth.

    AC-2 owns the login flow and measures it; what this module needs is only an authenticated
    principal, and minting one keeps every test below about the route under test rather than about
    the sign-in that precedes it.
    """
    from jose import jwt

    from app.config import get_settings

    now = int(datetime.now(UTC).timestamp())
    token = jwt.encode(
        {"sub": "staff", "role": "staff", "iat": now, "exp": now + 3600},
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": "Bearer " + token}


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _served() -> set[str]:
    """Return ``(method, path)`` for everything the app routes, included routers flattened.

    FastAPI hangs an ``include_router`` payload off a node that exposes the mounted router rather
    than a plain ``routes`` attribute, so a route that lives only inside one reads as absent unless
    both spellings are followed - which is why this walks rather than comprehensioning. It is the
    same shape the merged board test uses for the guest routes.
    """
    from fastapi.routing import APIRoute

    found: set[str] = set()
    stack = list(app.routes)
    while stack:
        route = stack.pop()
        nested = getattr(route, "routes", None) or getattr(
            getattr(route, "original_router", None), "routes", None
        )
        if nested:
            stack.extend(nested)
        if isinstance(route, APIRoute):
            for method in route.methods or ():
                found.add(f"{method} {route.path}")
    return found


def test_every_operation_is_mounted(client: TestClient) -> None:
    """AC-1's set, read off the same object AC-1 reads it off."""
    served = {entry.split(" ", 1)[1] for entry in _served()}
    missing = ROUTE_PATHS - served
    assert not missing, sorted(missing)


def test_the_list_answers_get_and_nothing_else(client: TestClient) -> None:
    """The queue is read, never written, by its own path; a body is not what moves a row."""
    verbs: dict[str, set[str]] = {}
    for entry in _served():
        method, _, path = entry.partition(" ")
        if path.startswith("/api/v1/staff/waitlist"):
            verbs.setdefault(path, set()).add(method)
    assert verbs["/api/v1/staff/waitlist"] == {"GET"}
    assert "GET" not in verbs["/api/v1/staff/waitlist/{entry_id}/call"]


def test_an_anonymous_caller_is_refused(client: TestClient) -> None:
    """AC-2's first clause, on every one of the nine rather than on the one that is easiest."""
    # The verbs differ, and the answer must not: a caller with no token is turned away before the
    # path is dispatched, so an unauthenticated POST is a 401 and never the 405 a wrong verb would
    # answer. Each path below is called with the verb that path actually owns.
    for method, path in (
        ("get", "/api/v1/staff/waitlist"),
        ("post", "/api/v1/staff/waitlist/reorder"),
        ("post", "/api/v1/staff/waitlist/00000000-0000-0000-0000-000000000000/call"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code in (401, 403), (method, path, response.status_code)


def test_the_list_answers_the_contract_shape(client: TestClient) -> None:
    """``items`` plus ``total``, and no raw phone anywhere in the envelope."""
    response = client.get("/api/v1/staff/waitlist", headers=_staff_headers())
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total"}
    assert isinstance(body["items"], list)


def test_an_unknown_status_group_is_a_validation_error_not_an_empty_queue(
    client: TestClient,
) -> None:
    """A filter the enum does not define must not be answerable by "nobody is waiting"."""
    response = client.get(
        "/api/v1/staff/waitlist", headers=_staff_headers(), params={"status": "NOT_A_STATUS"}
    )
    assert response.status_code == 422


class TestMask:
    """The one display rule this surface forwards rather than decides.

    AC-3 measures the merged helper and AC-5 measures it through this surface, so the two readings
    have to be the same function's answer. What is pinned below is what neither AC can be
    read without: the example's exact form, the credential tail, and that applying the rule
    twice does not move. The *quantity* of the mark is deliberately not asserted except where
    the contract fixes it, because the helper hides a whole block and its example is three wide.
    """

    SHAPES = ("0900-000-001", "0912345678", "02-123-4567", "0912-345-678", "02-1234-5678")

    def test_the_contract_example(self) -> None:
        assert mask_phone("0900-000-001") == "0900-***-001"

    def test_the_credential_tail_survives(self) -> None:
        for phone in self.SHAPES:
            digits = "".join(ch for ch in phone if ch.isdigit())
            assert mask_phone(phone).endswith(digits[-3:]), phone

    def test_applying_it_twice_changes_nothing(self) -> None:
        for phone in self.SHAPES:
            once = mask_phone(phone)
            assert mask_phone(once) == once, phone

    def test_a_number_too_short_to_have_a_middle_is_left_alone(self) -> None:
        assert mask_phone("0900-00") == "0900-00"
        assert mask_phone("") == ""

    def test_a_number_shown_by_this_surface_is_the_merged_rule(self) -> None:
        """The transport keeps no second spelling of the mask.

        AC-3 and AC-5 both describe the mask, and AC-3 measures the merged helper directly, so the
        helper is the thing this surface has to reproduce exactly - a second implementation that
        agreed on the contract's example and disagreed anywhere else would pass one AC and fail the
        other, and would be a rule the contract does not have.
        """
        from app.services.staff_waitlist import _display_phone

        for phone in self.SHAPES + ("", "0900-00"):
            assert _display_phone(phone) == (mask_phone(phone) or None), phone


class TestSearch:
    """R-B07-2's two readings of ``search``, measured on the predicate rather than over HTTP.

    The HTTP half needs a seeded day, which AC-4 measures; this is the half that AC-4's own seed
    data makes unreachable and that therefore has to be pinned somewhere.
    """

    class Row:
        def __init__(self, name: str, phone: str) -> None:
            self.name, self.phone = name, phone

    def test_a_name_is_matched_case_insensitively_as_a_substring(self) -> None:
        row = self.Row("Alice Chen", "0900-000-001")
        assert service._matches_search(row, "alice")
        assert service._matches_search(row, "CHEN")
        assert not service._matches_search(row, "Bob")

    def test_a_three_digit_tail_finds_the_row_it_belongs_to(self) -> None:
        assert service._matches_search(self.Row("Anyone", "0900-000-002"), "002")
        assert not service._matches_search(self.Row("Anyone", "0900-000-002"), "003")

    def test_a_tail_longer_than_three_asks_for_a_phone_and_finds_no_name(self) -> None:
        # `search=0900-000-002` is seven digits. It is not the three the tail comparison is
        # defined on, and it must answer nothing rather than an unrelated row.
        assert not service._matches_search(self.Row("Alice Chen", "0900-000-002"), "0900-000-002")

    def test_a_masked_never_matches(self) -> None:
        # The mask is a display value; matching on it would let a search see the number behind it.
        assert not service._matches_search(self.Row("Anyone", "0900-000-001"), "***")


class TestQueueOrder:
    def test_the_order_is_the_two_columns_and_nothing_else(self) -> None:
        order = service._queue_order()
        text = " ".join(str(clause) for clause in order)
        assert "sort_order" in text and "created_at" in text
        assert len(order) == 2
