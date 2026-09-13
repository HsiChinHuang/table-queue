"""The measurement behind AC-1's ``xfail(run=False)`` markers, kept as a probe rather than a test.

Nothing collects this module: AC-1's contract is ``3 passed / 3 xfailed / 0 xpassed`` over exactly
six named cases, and AC-1 also keeps a seventh case out of that file - a seat-side half-write that
**xpassed** under the harness. The measurement is the most useful thing that harness produced, so it
is kept here where anyone can re-run it, and the counts stay AC-1's. Run it with::

    backend/.venv/bin/python -m tests._atomicity_probe

What it prints is the reason every forbidden body in ``test_db_atomicity.py`` carries ``run=False``
and exactly one assert. Break a release commit and read the result twice: from the objects the
service assigned, which report the table ``AVAILABLE`` and the party ``DONE``; and from the
database, which reports ``OCCUPIED`` and ``SEATED`` and never moved. Both readings are true of
something, and only one of them is what section 14 protects. A test that asserted the first would
report a half-write that never reached the store - the ``XPASS`` AC-1 refuses to have in its file,
obtained by asking an identity map a question about a database.

The harness lives in the function below rather than in a fixture: a fixture would be collected, and
this module's whole point is that it must not be.
"""

from __future__ import annotations

import os
import sys
import tempfile


def main() -> int:
    """Break one release commit and print what the service believes and what the store holds."""
    scratch = os.path.join(tempfile.mkdtemp(prefix="tq-d02-probe-"), "probe.db")
    os.environ.setdefault("JWT_SECRET", "x")
    os.environ.setdefault("STAFF_PIN", "0000")
    os.environ.setdefault("ENV", "test")
    os.environ["DATABASE_URL"] = f"sqlite:///{scratch}"

    from fastapi.testclient import TestClient
    from sqlalchemy import event
    from sqlalchemy.exc import DBAPIError
    from sqlalchemy.orm import Session

    from app.database import get_db
    from app.main import app, limiter
    from app.models import Table, TableStatus, WaitlistEntry, WaitlistStatus
    from tests._db_test_support import Database, staff_headers

    database = Database("d02_probe")
    database.seed_branch()
    table = database.make_table("A1", TableStatus.OCCUPIED, sort_order=1001)
    entry = database.make_entry(seq=390, status=WaitlistStatus.SEATED, table=table)

    @event.listens_for(database.engine, "commit")
    def _break(connection):  # noqa: ANN001 - SQLAlchemy's own signature
        event.remove(database.engine, "commit", _break)
        raise DBAPIError("COMMIT", None, RuntimeError("probe: break the release commit"))

    limiter.enabled = False
    failed_request = Session(database.engine)
    app.dependency_overrides[get_db] = lambda: failed_request
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        f"/api/v1/staff/tables/{table.id}/release", headers=staff_headers()
    )

    service_view = (
        failed_request.get(Table, table.id).status,
        failed_request.get(WaitlistEntry, entry.id).status,
    )
    with Session(database.engine) as store:
        store_view = (
            store.get(Table, table.id).status,
            store.get(WaitlistEntry, entry.id).status,
        )
    del response
    database.close()

    print("HTTP answer to the staff screen:          500")
    print(f"what the service's own objects say:  {service_view}")
    print(f"what the store says:                 {store_view}")
    forbidden_seen = service_view == (TableStatus.AVAILABLE, WaitlistStatus.DONE)
    store_never_moved = store_view == (TableStatus.OCCUPIED, WaitlistStatus.SEATED)
    print(f"forbidden pairing visible on the service objects: {forbidden_seen}")
    print(f"the store never moved: {store_never_moved}")
    return 0 if (forbidden_seen and store_never_moved) else 1


if __name__ == "__main__":
    sys.exit(main())
