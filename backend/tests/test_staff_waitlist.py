"""The staff waitlist transport: the nine routes, and the two rules they carry.

AC-15 names this file. It is deliberately not a restatement of the issue's own AC blocks - those
mount the app from a scratch directory and drive it through ``TestClient``, and they are the
acceptance gate. What belongs here is the narrow behaviour the transport owns and that nothing else
in the suite touches: which paths exist, which verb each answers, who is allowed in, and the two
places where a response shape is decided rather than passed through - the mask, and the session
recovery that keeps a read from answering "nobody is waiting".

Everything status-shaped - call, seat, no-show, restore, revert, cancel, reorder - is measured by
the issue's AC-6 through AC-13 against a real database and is not repeated here. The one exception
is ``TestEditBody``: the PUT edit route's body rules are AC-6, AC-7 and AC-13's subject, and the
round-3 gate passed with 14 greens while that route answered 500 on every request that carried a
body, because nothing in this module PUT anything. A defect that only the suite can catch has to be
one the suite actually drives, so the PUT is exercised here too, over a database the test owns.
"""

from __future__ import annotations

import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app, limiter
from app.models import Branch, Restaurant, WaitlistEntry, WaitlistSource, WaitlistStatus
from app.models import Settings as SettingsRow
from app.schemas import mask_phone
from app.services import staff_waitlist as service

DAY = "20260910"

# The nine operations of R-B07-1, as AC-1 reads them off app.routes.
ROUTE_PATHS = {
    "/api/v1/staff/waitlist",
    "/api/v1/staff/waitlist/reorder",
    "/api/v1/staff/waitlist/{entry_id}",
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


class TestEditBody:
    """AC-6/AC-7/AC-13's edit route, driven over HTTP from inside the suite.

    Why this class exists at all: the round-3 gate reported fourteen greens while
    ``PUT /api/v1/staff/waitlist/{entry_id}`` answered 500 ``INTERNAL_ERROR`` for every request that
    carried a body - the endpoint read ``request.body()`` without awaiting it, in a ``def`` handler
    with no loop to await on. Nothing in this module PUT anything, so the suite was blind to it and
    only the issue's own AC blocks saw the red. These two tests are the half the suite has to own:
    the 422 a rejected body must answer, and the 200 plus read-back a legal one must answer.

    Ownership, per ``_docs/testing.md``: the module owns its engine, its schema and its
    ``get_db`` override, and restores the override and ``limiter.enabled`` on teardown. It never
    touches ``app.database.engine`` and never calls ``os.environ.setdefault``. The engine is a
    class singleton over a file under ``tempfile.mkdtemp()`` rather than a function-scoped one,
    because the module's plain ``TestClient(app)`` tests build a client with no ``get_db``
    override: disposing a ``StaticPool`` engine underneath a client another test still holds is
    how ``test_the_list_answers_the_contract_shape`` would start answering "no such table".

    The 500 that this class exists for is a body-read bug, so the ``async def`` edit endpoint has
    to be driven by an event loop - which is exactly what ``TestClient`` provides, and what a
    direct service call would not.
    """

    EDIT = "/api/v1/staff/waitlist/"

    _engine: ClassVar[Engine | None] = None
    """The one engine this class builds: created on first use, dropped when the module finishes."""

    @classmethod
    def _shared_engine(cls) -> Engine:
        """Create - once per run - the SQLite file the edit tests share."""
        if cls._engine is None:
            dbfile = Path(tempfile.mkdtemp(prefix="tq_b07_edit_")) / "b07_edit.db"
            cls._engine = create_engine(
                f"sqlite:///{dbfile}",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            Base.metadata.create_all(cls._engine)
        return cls._engine

    @classmethod
    def teardown_class(cls) -> None:
        """Dispose that engine when the class is done, so nothing outlives the run."""
        if cls._engine is not None:
            cls._engine.dispose()
            cls._engine = None

    @pytest.fixture()
    def db(self, request):
        """A session on the class schema, cleared of the previous test's rows first.

        ``del request`` is fixture-ordering only. The ``delete`` of every waitlist row is what makes
        a read-back a measurement rather than a recount of whatever an earlier test wrote; the
        restaurant, branch and settings row are the singletons the queue reads to name its day, its
        hold and its prefix, so they are written only when absent and shared on purpose.
        """
        del request
        session = sessionmaker(bind=self._shared_engine())()
        session.query(WaitlistEntry).delete()
        if session.get(Restaurant, 1) is None:
            session.add(Restaurant(id=1, name="R"))
        if session.get(Branch, 1) is None:
            session.add(
                Branch(
                    id=1,
                    restaurant_id=1,
                    name="B",
                    address="a",
                    phone="p",
                    timezone="Asia/Taipei",
                    business_day_cutoff_hour=4,
                    open_time="11:00",
                    close_time="21:00",
                )
            )
        if session.query(SettingsRow).first() is None:
            session.add(
                SettingsRow(
                    branch_id=1,
                    hold_minutes=10,
                    avg_seat_minutes=15,
                    queue_prefix="A",
                    is_waitlist_open=True,
                    sound_enabled_default=True,
                    notification_templates="{}",
                    staff_pin_hash=None,
                )
            )
        session.commit()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture()
    def client(self, db):
        """A client bound to this test's session, with the limiter muted for the call only."""
        previous_enabled = limiter.enabled
        limiter.enabled = False
        app.dependency_overrides[get_db] = lambda: db
        try:
            yield TestClient(app, raise_server_exceptions=False)
        finally:
            app.dependency_overrides.pop(get_db, None)
            limiter.enabled = previous_enabled

    @staticmethod
    def _headers() -> dict[str, str]:
        """A staff bearer minted from the environment's own secret (AC-2 owns the login flow)."""
        now = int(time.time())
        token = jwt.encode(
            {"sub": "staff", "role": "staff", "iat": now, "exp": now + 3600},
            os.environ["JWT_SECRET"],
            algorithm="HS256",
        )
        return {"Authorization": "Bearer " + token}

    @staticmethod
    def _entry(db, *, status: WaitlistStatus, party_size: int = 2) -> WaitlistEntry:
        """One row on the live business day, so the queue and the edit both see it."""
        row = WaitlistEntry(
            branch_id=1,
            queue_number="A001",
            full_queue_number="A-20260910-001",
            queue_prefix="A",
            seq=1,
            business_date=service._queue_day(db),
            name="Guest",
            phone="0900-000-001",
            party_size=party_size,
            status=status,
            sort_order=1,
            source=WaitlistSource.STAFF,
        )
        db.add(row)
        db.commit()
        return row

    def test_a_status_key_is_refused_and_writes_nothing(self, client, db) -> None:
        """AC-6: a ``status`` in the body is 422 ``VALIDATION_ERROR``, not a coercion, not a 500."""
        entry = self._entry(db, status=WaitlistStatus.WAITING)
        response = client.put(
            self.EDIT + str(entry.id), headers=self._headers(), json={"status": "ACTIVE"}
        )
        assert response.status_code == 422, response.text
        payload = response.json()
        assert "detail" not in payload, payload
        assert payload["error"]["code"] == "VALIDATION_ERROR"
        assert payload["error"]["message"]
        db.expire_all()
        assert db.get(WaitlistEntry, entry.id).status is WaitlistStatus.WAITING

    def test_an_out_of_range_party_size_is_refused_and_writes_nothing(self, client, db) -> None:
        """AC-7/AC-13: ``EditWaitlistRequest`` is ge=1, le=5, and its own 422 has to reach the wire.

        This is the arm that the un-awaited body read hid behind a 500: a legal JSON shape whose
        value breaks a declared constraint is the schema's answer, not the application's, so a 500
        here means the validation error never became the section 11 envelope.
        """
        entry = self._entry(db, status=WaitlistStatus.WAITING, party_size=2)
        for rejected in (0, 21):
            response = client.put(
                self.EDIT + str(entry.id),
                headers=self._headers(),
                json={"party_size": rejected},
            )
            assert response.status_code == 422, (rejected, response.text)
            payload = response.json()
            assert "detail" not in payload, payload
            assert payload["error"]["code"] == "VALIDATION_ERROR"
            db.expire_all()
            assert db.get(WaitlistEntry, entry.id).party_size == 2, rejected

    def test_a_legal_party_size_reaches_the_row_and_the_response(self, client, db) -> None:
        """AC-13: a legal edit from ``WAITING`` answers 200, and the row says what the body said."""
        entry = self._entry(db, status=WaitlistStatus.WAITING, party_size=2)
        response = client.put(
            self.EDIT + str(entry.id), headers=self._headers(), json={"party_size": 4}
        )
        assert response.status_code == 200, response.text
        assert response.json()["party_size"] == 4
        db.expire_all()
        row = db.get(WaitlistEntry, entry.id)
        assert row.party_size == 4
        assert row.status is WaitlistStatus.WAITING

    def test_an_empty_body_is_a_no_op_200(self, client, db) -> None:
        """AC-7 arm 11: ``{}`` edits nothing and answers the entry unchanged.

        The no-op is the other half of the absent-body rule the 500 swallowed: the endpoint must
        still answer 200 when there was nothing to apply, and it must apply nothing.
        """
        entry = self._entry(db, status=WaitlistStatus.CALLED, party_size=3)
        response = client.put(self.EDIT + str(entry.id), headers=self._headers(), json={})
        assert response.status_code == 200, response.text
        assert response.json()["party_size"] == 3
        db.expire_all()
        row = db.get(WaitlistEntry, entry.id)
        assert (row.party_size, row.note, row.status) == (3, None, WaitlistStatus.CALLED)

    def test_a_body_with_no_known_key_is_refused(self, client, db) -> None:
        """AC-7: a body that names no editable field is refused, not silently accepted."""
        entry = self._entry(db, status=WaitlistStatus.WAITING)
        response = client.put(
            self.EDIT + str(entry.id), headers=self._headers(), json={"table_id": "x"}
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_a_seated_entry_refuses_the_edit_with_409(self, client, db) -> None:
        """AC-13 arm 2: the state gate is a 409, and the refused row keeps its party size."""
        entry = self._entry(db, status=WaitlistStatus.SEATED, party_size=5)
        response = client.put(
            self.EDIT + str(entry.id), headers=self._headers(), json={"party_size": 2}
        )
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "WAITLIST_INVALID_STATUS"
        db.expire_all()
        assert db.get(WaitlistEntry, entry.id).party_size == 5

    def test_the_edit_route_is_the_put_and_the_post_edit_spelling_is_gone(self) -> None:
        """AC-14's route inventory, from the suite: only the PUT edit is served.

        ``_docs/openapi.yaml`` declares ``PUT /api/v1/staff/waitlist/{id}`` and no ``/edit``, and
        B-12's contract-completeness test fails the whole suite on a served-but-undeclared path.
        Pinning it here means a re-added compatibility alias is a red test in this module, in the
        file that owns the surface, rather than a merge-gate failure two issues away.
        """
        served = _served()
        assert "PUT /api/v1/staff/waitlist/{entry_id}" in served
        assert not [
            entry for entry in served if entry.endswith("/api/v1/staff/waitlist/{entry_id}/edit")
        ], sorted(entry for entry in served if entry.endswith("/edit"))


