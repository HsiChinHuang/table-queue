# Setup

## Prerequisites

- git >= 2.20 (worktree support)
- Tech-stack toolchain (uv / npm / etc., per `plan.md`)

### Getting `uv` (the one prerequisite a fresh machine usually lacks)

`uv` is the installer this repo ships an `uv.lock` for, and `make setup` needs it on `PATH`. It is not
part of a default Linux or WSL image:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # installs into ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"               # only if ~/.local/bin is not already on PATH
uv --version                                       # must print a version, not "command not found"
```

Every `make` target that needs uv calls a guard first: if `uv` is not on `PATH` the target stops with
"'uv' is not on PATH" and the install line above, rather than writing a half-built environment. Nothing
in the Makefile hardcodes a user's home directory, so the same commands work for any contributor.

### TableQueue run surface (backend + frontend)

The application checkout has its own one-time bootstrap, documented in `README.md` and summarised here:

```bash
cp backend/.env.example backend/.env      # gitignored; the app will not boot without it
# then set in backend/.env:
#   JWT_SECRET=...   at least 32 chars: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
#   STAFF_PIN=...    no default and no example value (T9/D-1)
make setup                                # backend/.venv via `uv sync --project backend` + frontend `npm ci`
make seed                                 # reset + seed backend/dev.db
make dev                                  # backend :8000 and frontend :5173 together
```

- `make setup` runs `uv sync --project backend`, which builds the environment at `backend/.venv`
  (uv's `<project>/.venv` rule) and reads `[dependency-groups] dev`; `pip install -e backend` cannot read
  that group and would leave pytest/ruff out of the interpreter the run surface uses.
- `make setup SKIP_FRONTEND=1` bootstraps the backend only, for hosts where npm is unavailable.
- Node: `.nvmrc` pins 20 (`nvm use`); system node 18 cannot run vite.
- Frontend tests: `cd frontend && npm run test -- --run` — bare `npm run test` is watch mode and never
  exits. `make test-frontend` and the root `npm run test:frontend` already pass `--run`.
- Exit codes: run a target bare and read `$?` (or redirect to a log). Piping a target into `head`/`tail`
  reports the consumer's status and hides a failing target.

Env vars:
  | Var | Required | Purpose |
  |---|---|---|
  | `PLATFORM` | yes | `github` or `gitlab` |
  | `API_TOKEN` | yes | Access token |
  | `REPO_ID` | yes | GitHub: `owner/repo`; GitLab: numeric project ID |
  | `API_URL` | no | Self-hosted only |
  | `APPROVAL_MODE` | no | `full-auto` (default) / `semi-auto` / `manual` |

## Steps

1. Copy `.env.example` to `.env`, fill in required values.
2. Copy `_docs/config.yaml.example` to `_docs/config.yaml` (optional; defaults used if absent).
3. Write `_docs/requirements.md` (use `requirements.md.example`).
4. Start Orchestrator (external launcher passes `_docs/team/orchestrator.md`).
5. Orchestrator runs preflight, then SA generates `plan.md` + `issues/`.
6. Review generated issues. If satisfied, create `_docs/state/initialized`.

## Config

- Precedence: env > `config.yaml` > `config.yaml.example`.
- Only listed keys are env-overridable (see `_docs/config.md`).
- Missing `config.yaml`: Orchestrator uses `.example` defaults (does not HALT).
- Secrets (`API_TOKEN`) only from env, never yaml.
- Config read at boot only; changes require restart.

Permissions:

- `.env`: 600 (owner only). World-readable -> warn.
- `_docs/config.yaml`: 644 acceptable.

## Modes

| Mode | Behavior |
|---|---|
| `full-auto` (default) | No human approval required |
| `semi-auto` | Merge, deps, delete, CI changes require approval |
| `manual` | Every merge requires approval |

Set via env: `APPROVAL_MODE=semi-auto`.

## First-run checklist

- [ ] `_docs/requirements.md` exists
- [ ] `_docs/plan.md.example` exists
- [ ] `_docs/task-template.md` exists
- [ ] Env vars set (`PLATFORM`, `API_TOKEN`, `REPO_ID`)
- [ ] `git remote origin` configured
- [ ] `git worktree` supported (`git --version` >= 2.20)
- [ ] `.env` permissions 600

## Token rotation

1. Update `API_TOKEN` in `.env`.
2. Restart Orchestrator.
3. If in-flight issues exist, Orchestrator uses new token on resume.
No special procedure required.

## Completion

When all issues close: Orchestrator writes `_docs/state/COMPLETE.md` and stops.
To resume: delete `COMPLETE.md` and restart.

Details: `_docs/team/orchestrator-human.md` Sec. 5.

## Reset

To reset project state:
1. Create `_docs/state/RESET` file.
2. Create `_docs/state/RESET_APPROVED` file.
3. Orchestrator archives current state to `_docs/state/history/<ts>/`, then restarts SA.
Config (`.env`, `config.yaml`) is NOT reset.

## Human controls

| Control | File |
|---|---|
| Pause | `_docs/state/PAUSE` |
| Resume | delete `PAUSE` |
| Restart | `_docs/state/RESTART` |
| Reset | `_docs/state/RESET` + `RESET_APPROVED` |
| Approvals | `_docs/state/APPROVALS.md` |
| Cancel subagent | `_docs/state/CANCEL_<issue_id>` |

Full spec: `_docs/team/orchestrator-human.md`.