# Commands

Commands are defined by `plan.md` tech-stack. Defaults:

## Python

- `uv sync` - install dependencies
- `uv run pytest` - whole suite
- `ruff check --fix` - lint and autofix

## Git (universal)

- `git worktree add ../worktrees/<ID> -b issue/<ID>-<slug>` - create worktree
- `git push -u origin issue/<ID>-<slug>` - push branch
- `git fetch origin` - sync remote
- `git checkout main && git reset --hard origin/main` - sync main
- `git merge --no-ff issue/<ID>-<slug>` - merge branch
- `git worktree remove ../worktrees/<ID>` - cleanup

For non-Python: replace with equivalent in `plan.md`.

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
