# Commands

Defaults per tech-stack. Override in `plan.md` if different.

## Python (default)

Commands run from the repository root. `uv sync` in `backend/` creates `backend/.venv`, and that venv is
the interpreter everything here uses; uv's environment resolution is only the fallback when no venv has been created yet.
This platform has no `python` executable at all, only `python3`.

| Purpose | Command |
|---|---|
| Create/refresh venv + dev group | `uv sync --project backend` (what the bootstrap target runs; creates `backend/.venv`) |
| Run all tests | `cd backend && .venv/bin/python -m pytest -q` |
| Run one file | `cd backend && .venv/bin/python -m pytest tests/test_<name>.py` |
| Run one test | `cd backend && .venv/bin/python -m pytest tests/test_<name>.py::<Class>::<test>` |
| Lint | `cd backend && .venv/bin/python -m ruff check .` |
| Lint + fix | `cd backend && .venv/bin/python -m ruff check --fix .` |
| Lint JSON | `cd backend && .venv/bin/python -m ruff check --output-format=json .` |

## Git (universal)

| Purpose | Command |
|---|---|
| Create worktree | `git worktree add ../worktrees/<ID> -b issue/<ID>-<slug>` |
| Push branch | `git push -u origin issue/<ID>-<slug>` |
| Sync remote | `git fetch origin` |
| Sync main | `git checkout main && git reset --hard origin/main` |
| Merge branch | `git merge --no-ff issue/<ID>-<slug>` |
| Remove worktree | `git worktree remove ../worktrees/<ID>` |

## Non-Python

Replace with equivalents defined in `plan.md` tech-stack section.

## Orchestrator commands

| Purpose | Command |
|---|---|
| Export failures | `orchestrator export-failures` |
| Generate DAG | `orchestrator dag-export` |
| Heartbeat | (handled by subagent internally) |


## Project make targets (TableQueue)

All targets run from the repo root; `Makefile`, `backend/`, `frontend/` and the root `package.json` came
from Platform Issue 12 (F-01, closed). The setup target bootstraps both toolchains and every other target
works from that bootstrap plus a real `backend/.env` (`_docs/SETUP.md` lists the two values without
examples). Manual equivalents are the same commands without make.

Each row names the target to prefix with `make`; every command below is run bare so its rc is
assertable (see the next section).

| Task | Target | Manual equivalent |
|---|---|---|
| Install both toolchains | setup | `uv sync --project backend`; `cd frontend && npm ci` |
| Run backend and frontend | dev | two terminals: `cd backend && .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0`; `cd frontend && ./node_modules/.bin/vite --port 5173` |
| Backend only / frontend only | backend / frontend | see the dev row |
| Reset and seed database | seed | `cd backend && .venv/bin/python -m app.seed --reset` |
| All tests | test | `cd backend && .venv/bin/python -m pytest -q`; `cd frontend && npm run test -- --run` |
| Backend tests / frontend tests | test-backend / test-frontend | as above |
| Lint | lint | `cd backend && .venv/bin/python -m ruff check .`; `cd frontend && npm run lint` (frontend lint is pinned red until T22) |
| Format | format | `cd backend && .venv/bin/python -m ruff format .`; `cd frontend && npm run format` |

### Exit codes, pipes, and watch mode

Documented make invocations are run bare and their exit code is asserted directly (`cmd > /tmp/tq-run.log 2>&1; echo "rc=$?"`). Wrapping one in a pipe to `head` or `tail` is a documentation bug: the pipe reports the consumer's status, so a red target looks green. The same rule covers the manual equivalents below and in `_docs/commands.md`.

```bash
set +e
make test-backend > /tmp/tq-be.log 2>&1
echo "rc=$?"          # rc=0 is the pass marker; taken before the log is read
```

Second trap: `cd frontend && npm run test` is bare vitest in watch mode and never exits, so the
documented one-pass command is `cd frontend && npm run test -- --run`. `test-frontend` and the root
`npm run test:frontend` already pass `--run`; the frontend `package.json` is outside this issue's
allowed files, which is why the flag is carried by every caller instead.

Commands reference: `_docs/requirements.md` section 6, `_docs/testing.md` section 8, `_docs/plan.md`
F-01. Environment specifics (`uv` on `PATH`, `python3` vs `python`, which filesystem may host a
toolchain) are recorded in `_docs/orchestrator-playbook.md` and repeated in each issue brief.
