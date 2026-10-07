#!/usr/bin/env python3
"""
Recover orphaned subagent runs after Orchestrator restart or crash.

This script enumerates pi-subagents run directories, filters to runs that
belong to this project and are still in "running" state, and reports them
for the Orchestrator to reconcile against snapshot.json.

Usage:
    python scripts/recover_orphans.py

Output (stdout):
    JSON array of orphan candidates:
    [
      {
        "run_id": "b0c73a06",
        "agent": "builder",
        "state": "running",
        "last_activity_ms": 1728200000000,
        "deadline_ms": 1728201800000,
        "pid": 29416,
        "elapsed_since_activity_ms": 420000
      },
      ...
    ]

Exit codes:
    0 - script ran successfully (may or may not have found orphans)
    1 - configuration error (missing env, project root not found)
"""

import json
import os
import sys
import glob
import time


# pi-subagents stores runs under a user-scoped directory.
# Path pattern varies by OS; keep both variants here.
RUNS_DIR_CANDIDATES = [
    os.path.expandvars(r"%TEMP%\pi-subagents-user-%USERNAME%\async-subagent-runs"),
    os.path.expanduser("~/.cache/pi-subagents/async-subagent-runs"),
    "/tmp/pi-subagents/async-subagent-runs",
]


def find_runs_dir():
    for cand in RUNS_DIR_CANDIDATES:
        if os.path.isdir(cand):
            return cand
    return None


def project_root():
    """Return the absolute path of the current project root."""
    return os.path.abspath(os.getcwd())


def load_status(status_path):
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def main():
    runs_dir = find_runs_dir()
    if not runs_dir:
        print(
            "ERROR: pi-subagents runs directory not found. "
            "Checked: " + ", ".join(RUNS_DIR_CANDIDATES),
            file=sys.stderr,
        )
        return 1

    project = project_root()
    now_ms = int(time.time() * 1000)

    orphans = []
    pattern = os.path.join(runs_dir, "*", "status.json")
    for status_path in glob.glob(pattern):
        s = load_status(status_path)
        if not s:
            continue
        if s.get("state") != "running":
            continue
        cwd = str(s.get("cwd", ""))
        if not cwd.startswith(project):
            continue

        # Extract agent from steps[0].agent (pi-subagents schema).
        steps = s.get("steps") or []
        agent = steps[0].get("agent") if steps else None

        last_activity = s.get("lastActivityAt", 0)
        deadline = s.get("deadlineAt", 0)

        orphans.append(
            {
                "run_id": s.get("runId"),
                "agent": agent,
                "state": s.get("state"),
                "last_activity_ms": last_activity,
                "deadline_ms": deadline,
                "pid": s.get("pid"),
                "elapsed_since_activity_ms": now_ms - last_activity,
            }
        )

    print(json.dumps(orphans, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())