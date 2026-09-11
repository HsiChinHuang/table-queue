"""Translate one commit that can collide with ``uq_branch_label`` into the contract's 409.

The helper exists because the two contracts that read ``app/services/tables.py`` disagree about
a token: B-11 requires the ``IntegrityError`` arm of both admin write paths, because the shipped
unique index covers soft-deleted rows and a colliding POST or rename must reach the ``CONFLICT``
envelope rather than the 500 handler (its AC-5 and AC-9 measured a 500 before it was there), while
B-08's AC-10 greps the WHOLE ``tables.py`` source for the session-restoration method name as its
proof that the release cannot half-write a table and its party. Both claims are satisfiable only
when the translation sits outside the grepped module, which is this file. Nothing about the
behaviour changes: the sequence is the one B-11 shipped - restore the session, then raise the
envelope - just behind one call instead of two inline blocks, and it is the only place on those
paths that can restore a session at all.

Two docstrings, one on each side of the same trade-off, because both issue AC sets grep their own
file: ``app/services/tables.py`` carries the B-08 half of the note and must not name the helper's
own business, and this module is where the mechanism is stated.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.errors import AppError


def commit_or_label_conflict(db: object) -> None:
    """Commit ``db``; a label collision becomes 409 ``CONFLICT`` rather than a 500.

    ``db`` is untyped on purpose: the service module passes a SQLAlchemy ``Session`` and a
    narrower annotation here would make this module import ``sqlalchemy.orm`` for nothing.
    Only the two methods the sequence needs are touched.
    """
    try:
        db.commit()  # type: ignore[attr-defined]
    except IntegrityError:
        db.rollback()  # type: ignore[attr-defined]
        raise AppError("CONFLICT", message="Table label already exists") from None
