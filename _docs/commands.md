# Commands

Defaults per tech-stack. Override in `plan.md` if different.

## Python (default)

| Purpose | Command |
|---|---|
| Install deps | `uv sync` |
| Run all tests | `uv run pytest` |
| Run one file | `uv run pytest tests/test_<name>.py` |
| Run one test | `uv run pytest tests/test_<name>.py::<Class>::<test>` |
| Lint + fix | `ruff check --fix` |
| Lint JSON | `ruff check --output-format=json` |

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

Copied verbatim from the old `AGENTS.md` section 6, now archived in `_docs/project-guide.md`. All
targets run from the repo root; `Makefile`, `backend/`, `frontend/` and the root `package.json` came
from Platform Issue 12 (F-01, closed).

| Task | Command | Manual equivalent |
|---|---|---|
| Install both toolchains | `make setup` | `cd backend && uv sync`, `cd frontend && npm install`, `npm install` |
| Run backend and frontend | `make dev` | `cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0`; `cd frontend && npm run dev -- --host` |
| Backend only / frontend only | `make backend` / `make frontend` | see `make dev` |
| Reset and seed database | `make seed` | `cd backend && uv run python -m app.seed --reset` |
| All tests | `make test` | `cd backend && uv run pytest`; `cd frontend && npm run test` |
| Backend tests / frontend tests | `make test-backend` / `make test-frontend` | as above |
| Lint | `make lint` | `cd frontend && npm run lint` (backend: `ruff check .`) |
| Format | `make format` | `cd frontend && npm run format` (backend: `ruff format`) |

Commands reference: `_docs/requirements.md` section 6, `_docs/testing.md` section 8, `_docs/plan.md`
F-01. Environment specifics (`uv` on `PATH`, `python3` vs `python`, which filesystem may host a
toolchain) are recorded in `_docs/orchestrator-playbook.md` and repeated in each issue brief.
