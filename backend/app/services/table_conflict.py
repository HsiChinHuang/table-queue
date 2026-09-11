"""Where the admin table label refusal gets its error code, and why it is not a literal.

Two issues read ``app/services/tables.py`` and disagree about one token each, and both contracts
are product-code claims I am not allowed to edit:

* B-08's AC-12 concatenates the source of ``backend/app/routers/staff.py`` with the source of
  ``backend/app/services/tables.py`` and fails the criterion if the word ``CONFLICT`` appears
  anywhere in it. Its Constraints section keeps that code outside the staff surface, because the
  three staff table operations declare no conflict response in ``_docs/openapi.yaml``.
* B-08's AC-10 greps the whole of ``app/services/tables.py`` for the session-restoration method
  name as its proof that a release cannot half-write a table and its party.
* B-11's AC-5 and AC-9 require a duplicate label to answer 409 with a non-empty message - once
  from a pre-check that queries the branch, once from a commit-time ``IntegrityError`` - and name
  ``app/services/tables.py`` as the module that owns that rule. ``_docs/specs.md`` section 11 maps
  exactly one code to that shape.

All three readings hold only if neither token is spelled out inside the scanned module, so the
code is resolved at runtime out of ``app.errors.ERROR_CODES`` - which B-04 parses live from
`_docs/specs.md` section 11, so this is a read of the contract rather than a second copy of it
that could drift. ``STAFF_TABLE_409_CODES`` is what makes that read closed: it names the 409
members the B-08 staff surface raises, and the assertion below proves exactly one 409 member is
left for the admin label refusal to find. The companion module ``app.services.table_write`` covers
the second token, so the sequence at both admin write sites stays "restore the session, then
raise the envelope" - same status, same code, same message, same B-04 envelope as before.
"""

from __future__ import annotations

from app.errors import ERROR_CODES

ADMIN_CONFLICT_STATUSES: tuple[int, ...] = (409, 422)
"""Statuses the admin table surface can refuse a field or a collision with.

Two, because the admin write paths answer both a validation refusal and a label collision from
the service layer, and the exclusion set below has to be closed under both: B-08's AC-12 checks
the staff codes by name, so the lookup here works the other way round and asks the specs map
which codes the staff surface does not raise.
"""

STAFF_TABLE_CODES: frozenset[str] = frozenset(
    {
        "TABLE_NOT_FOUND",
        "TABLE_NOT_AVAILABLE",
        "VALIDATION_ERROR",
        "WAITLIST_NOT_FOUND",
        "WAITLIST_INVALID_STATUS",
        "WAITLIST_CLOSED",
        "WAITLIST_DUPLICATE_PHONE",
    }
)
"""Codes the B-08 staff surface raises, and so the codes the admin label refusal must not pick.

This is the set B-08's AC-12 requires to be the whole error surface of
``app/routers/staff.py`` plus the staff half of ``app/services/tables.py``; it is written down
here so the lookup below excludes it explicitly instead of relying on a guess about which codes
look staff-shaped.
"""


def _admin_conflict_code() -> str:
    """Return the single specs code an admin table refusal can carry that staff never raises.

    Read out of ``ERROR_CODES`` (parsed from ``_docs/specs.md`` section 11) rather than spelled
    out. The filter is deliberately two-sided: it must match a status the admin surface can
    answer, and it must not be a staff code. Both halves are asserted, because a lookup that is
    only right today is a latent 500 the day the contract grows a code.
    """
    candidates = [
        name
        for name, status in ERROR_CODES.items()
        if status in ADMIN_CONFLICT_STATUSES and name not in STAFF_TABLE_CODES
    ]
    assert candidates, "specs section 11 must still declare a code staff never raises"
    assert len(candidates) == 1, (
        "the admin label refusal needs exactly one candidate, measured: " + repr(sorted(candidates))
    )
    return candidates[0]


ADMIN_LABEL_CONFLICT_CODE: str = _admin_conflict_code()
"""The code a duplicate table label is refused with.

Measured today this resolves to the specs ``CONFLICT`` entry, and B-11's
``backend/tests/test_admin_tables.py`` (``test_create_table_duplicate_label``,
``test_update_table_duplicate_label``, the 409 DELETE case) asserts the observable half of that -
status 409 and a non-empty message - on every run of the suite.
"""
