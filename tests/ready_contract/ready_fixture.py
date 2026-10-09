#!/usr/bin/env python3
"""Regression fixture for the ready.py readiness contract (t28 / platform #83).

Self-contained: Python 3 stdlib only, offline, no network/platform API.
Embeds a mini reference implementation of the contract pinned in
docs/tooling/ready-contract.md:

  1. closed-set = { id | id in issue-map AND platform state of the mapped
     number == "closed" }. Only source of "closed".
  2. Readiness is NEVER computed from issue titles.
  3. dep-map gap => per-issue UNKNOWN-deps report; other issues keep
     evaluating (no whole-run abort).

Usage:
  python3 tests/ready_contract/ready_fixture.py --case closed-bare-title
  python3 tests/ready_contract/ready_fixture.py --case dep-gap
  python3 tests/ready_contract/ready_fixture.py --case all

Exit 0 = all assertions for the case pass; 1 = violation.
"""

from __future__ import annotations

import argparse
import sys


# --- mini reference implementation of the contract -------------------------

def closed_set(issue_map: dict[str, int], platform_state: dict[int, str]) -> set[str]:
    """closed-set = ids whose mapped platform number has state 'closed'."""
    return {
        issue_id
        for issue_id, number in issue_map.items()
        if platform_state.get(number) == "closed"
    }


def evaluate_ready(
    issues: dict[str, str],
    issue_map: dict[str, int],
    platform_state: dict[int, str],
    dep_map: dict[str, list[str]],
) -> dict[str, str]:
    """Return {issue_id: status} for every non-closed issue.

    status in {"READY", "WAITING", "UNKNOWN-deps"}.
    Titles (`issues`) are accepted for reporting only and NEVER influence
    the result. A dep gap yields UNKNOWN-deps for that issue only.
    """
    closed = closed_set(issue_map, platform_state)
    result: dict[str, str] = {}
    for issue_id in issues:
        if issue_id in closed:
            continue  # closed issues never appear in readiness output
        deps = dep_map.get(issue_id)
        if deps is None:
            result[issue_id] = "UNKNOWN-deps"
            continue  # per-issue report; other issues keep evaluating
        unresolved = [d for d in deps if d not in issue_map or d not in closed]
        if any(d not in issue_map for d in deps):
            result[issue_id] = "UNKNOWN-deps"
        elif unresolved:
            result[issue_id] = "WAITING"
        else:
            result[issue_id] = "READY"
    return result


# --- fixture data -----------------------------------------------------------

def case_closed_bare_title() -> None:
    """Closed bare-title issues count closed; titles never flip classification.

    Includes the 4 observed reopens: B-15 #47, F-16 #48, P0-16 #49, P0-13 #46.
    """
    issue_map = {"B-15": 47, "F-16": 48, "P0-16": 49, "P0-13": 46, "T-1": 100}
    platform_state = {47: "closed", 48: "closed", 49: "closed", 46: "closed", 100: "open"}
    dep_map = {"T-1": []}
    # Bare (unbracketed) SA-era titles, exactly the shape that defeated the
    # old title regex:
    titles = {
        "B-15": "fix queue overflow on close day",
        "F-16": "staff view pagination",
        "P0-16": "waitlist cap enforcement",
        "P0-13": "reset endpoint auth",
        "T-1": "open issue",
    }
    result = evaluate_ready(titles, issue_map, platform_state, dep_map)

    for issue_id in ("B-15", "F-16", "P0-16", "P0-13"):
        assert issue_id not in result, f"{issue_id} is closed but appeared in readiness output"
    assert result.get("T-1") == "READY", f"T-1 should be READY, got {result.get('T-1')}"

    # Negative control: identical map/state data, different titles ->
    # identical classification. A title change can never flip an issue.
    titles_mutated = dict(titles)
    titles_mutated["B-15"] = "[x] fix queue overflow on close day (done)"
    titles_mutated["T-1"] = "[ ] totally different bracketed title"
    result_mutated = evaluate_ready(titles_mutated, issue_map, platform_state, dep_map)
    assert result_mutated == result, "classification changed when only titles changed"
    print("closed-bare-title: PASS (4 closed bare-title issues stay closed; title change is a no-op)")


def case_dep_gap() -> None:
    """Dep-map gap => UNKNOWN-deps for that issue only; others keep evaluating."""
    issue_map = {"A": 1, "B": 2, "C": 3, "D": 4}
    platform_state = {1: "closed", 2: "open", 3: "open", 4: "open"}
    dep_map = {
        "B": ["A"],      # dep closed -> READY
        "C": ["A", "X"], # X missing from dep-map/issue-map -> UNKNOWN-deps
        "D": ["B"],      # dep open -> WAITING
    }
    titles = {"A": "closed dep", "B": "ready one", "C": "gapped one", "D": "waiting one"}
    result = evaluate_ready(titles, issue_map, platform_state, dep_map)

    assert result.get("C") == "UNKNOWN-deps", f"C should be UNKNOWN-deps, got {result.get('C')}"
    assert result.get("B") == "READY", f"B should be READY, got {result.get('B')}"
    assert result.get("D") == "WAITING", f"D should be WAITING, got {result.get('D')}"
    assert "A" not in result, "closed issue A must not appear in readiness output"
    print("dep-gap: PASS (C=UNKNOWN-deps only; B=READY and D=WAITING still evaluated; no abort)")


CASES = {
    "closed-bare-title": case_closed_bare_title,
    "dep-gap": case_dep_gap,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[*CASES, "all"], default="all")
    args = parser.parse_args()
    selected = list(CASES.values()) if args.case == "all" else [CASES[args.case]]
    for case in selected:
        case()
    print(f"ready-contract fixture: ALL PASS ({args.case})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
