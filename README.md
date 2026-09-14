# TableQueue

Restaurant waitlist manager. Guest-facing waitlist join and status pages, staff dashboard for queue and tables, admin settings.

Built with FastAPI (Python + uv) and React (Node.js + Vite). Single-store MVP with `branch_id` reserved for future expansion.

---

## Overview

TableQueue handles the full waitlist flow:

- Guest joins via QR code or URL
- Guest sees live status and countdown when called
- Staff calls, seats, no-shows, restores, reverts, cancels
- Tables are tracked with manual status
- Public board shows current call
- Admin configures store info, waitlist rules, tables, PIN

All UI text is in English. Formats follow Taiwan localization (phone, timezone).

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, uv, SQLAlchemy 2.0, Pydantic v2, SQLite |
| Frontend | React 18, Vite, TypeScript, Tailwind, shadcn/ui, TanStack Query, Zustand |
| Auth | Single shared PIN → JWT |
| Testing | pytest (backend), Vitest + RTL (frontend) |
| Tooling | Makefile, concurrently, ruff, eslint, prettier |

---

## Project Structure

```
table-queue/
├── backend/
│ ├── pyproject.toml
│ ├── .env.example
│ ├── app/
│ │ ├── main.py
│ │ ├── config.py
│ │ ├── database.py
│ │ ├── models.py
│ │ ├── schemas.py
│ │ ├── dependencies.py
│ │ ├── errors.py
│ │ ├── routers/
│ │ │ ├── public.py
│ │ │ ├── staff.py
│ │ │ ├── admin.py
│ │ │ └── auth.py
│ │ ├── services/
│ │ │ ├── waitlist.py
│ │ │ ├── tables.py
│ │ │ └── settings.py
│ │ └── seed.py
│ └── tests/
│ ├── conftest.py
│ ├── factories.py
│ ├── test_auth.py
│ ├── test_public_waitlist.py
│ ├── test_staff_waitlist.py
│ ├── test_staff_tables.py
│ ├── test_admin_settings.py
│ └── test_state_machine.py
├── frontend/
│ ├── package.json
│ ├── vite.config.ts
│ ├── .env.example
│ ├── index.html
│ └── src/
│ ├── main.tsx
│ ├── App.tsx
│ ├── routes.ts
│ ├── api/
│ │ ├── client.ts
│ │ ├── errors.ts
│ │ ├── queryKeys.ts
│ │ ├── waitlist.ts
│ │ ├── tables.ts
│ │ ├── auth.ts
│ │ ├── settings.ts
│ │ └── mock/
│ ├── stores/
│ │ └── staffStore.ts
│ ├── layouts/
│ │ ├── PublicLayout.tsx
│ │ └── StaffLayout.tsx
│ ├── pages/
│ │ ├── public/
│ │ │ ├── JoinPage.tsx
│ │ │ ├── StatusPage.tsx
│ │ │ ├── LookupPage.tsx
│ │ │ └── BoardPage.tsx
│ │ ├── staff/
│ │ │ ├── LoginPage.tsx
│ │ │ ├── WaitlistPage.tsx
│ │ │ └── TablesPage.tsx
│ │ └── admin/
│ │ └── SettingsPage.tsx
│ ├── components/
│ │ ├── ui/
│ │ ├── WaitlistCard.tsx
│ │ ├── Countdown.tsx
│ │ ├── TableCard.tsx
│ │ ├── StatusBadge.tsx
│ │ ├── EmptyState.tsx
│ │ ├── LoadingSkeleton.tsx
│ │ ├── ConfirmDialog.tsx
│ │ ├── ConnectionBanner.tsx
│ │ ├── SoundToggle.tsx
│ │ ├── QrCode.tsx
│ │ └── DevBadge.tsx
│ ├── hooks/
│ │ ├── useWaitlist.ts
│ │ ├── useTables.ts
│ │ ├── useCountdown.ts
│ │ └── ...
│ └── lib/
│ ├── publicBaseUrl.ts
│ ├── format.ts
│ └── strings.ts
├── _docs/
│ ├── specs.md
│ ├── ui.md
│ ├── testing.md
│ ├── deployment.md
│ ├── openapi.yaml
│ ├── api-examples.md
│ ├── demo.md
│ └── issues/
├── Makefile
├── package.json
├── README.md
├── CONTRIBUTING.md
├── AGENTS.md
├── .editorconfig
├── .gitignore
└── .nvmrc
```

This tree is the full v1 target layout: it is a superset of _docs/requirements.md section 5, which lists the 53-entry core subset of these 102 entries.


---

## Getting Started

The `Makefile`, its targets, `backend/`, `frontend/` and the root `package.json` were delivered by F-01 (Platform Issue 12) and all of them are in this checkout, so the commands on this page are the commands that run.

### Prerequisites

- [uv](https://docs.astral.sh/uv/) - the Python installer this repo ships an `uv.lock` for. A fresh machine usually lacks it, and it is not on `PATH` by default:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh    # installs into ~/.local/bin
  export PATH="$HOME/.local/bin:$PATH"              # only if ~/.local/bin is not already on PATH
  uv --version                                        # must print a version, not "command not found"
  ```

  The setup target refuses with exactly that instruction when `uv` is missing (its recipe carries `exit 1`, so the failure is assertable as rc=1); it never hardcodes a machine-specific path.
- Python 3.12+ available as `python3` (this platform has no `python` alias; the run surface uses `python3` and `backend/.venv/bin/python`, never bare `python`)
- Node.js 20+ and `npm`. `.nvmrc` pins 20 - a system node 18 cannot run vite, so `nvm use` first.
- `make` - the targets below are the documented onboarding path, and the manual equivalents are listed next to each of them.

### One-time local configuration (git never fetches it)

`backend/.env` is gitignored, and since security audit A-1 / D-1 the app refuses to boot without two values that are deliberately not published anywhere:

```bash
cp backend/.env.example backend/.env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # paste the output as JWT_SECRET=
```

Then edit `backend/.env` so it carries `JWT_SECRET` (at least 32 characters; the published example values are refused) and `STAFF_PIN` (your own - no default, and it is a one-time seed for the staff credential, never an accepted login after the first boot). The seed, dev and backend targets check both before launching and name the missing one instead of letting the app fail mid-boot.

### Setup

```bash
set +e; make setup; rc=$?; echo "rc=$rc"   # assert the rc, never a pipe
```

That bootstrap creates `backend/.venv` with `uv sync --project backend` - `uv sync` builds the environment at `<project>/.venv`, which for this project is `backend/.venv`. uv is the installer that reads `[dependency-groups] dev` and puts pytest, ruff, httpx and freezegun into the same interpreter the run surface uses. `pip install -e backend` cannot read that group, so it is not the installer. The target then runs `cd frontend && npm ci`; pass `SKIP_FRONTEND=1` to bootstrap the backend alone on a host without npm.

Or manually:

```bash
cd backend && uv sync --project backend
cd frontend && npm ci
```

Run (foreground: it stays attached, Ctrl-C stops both servers)

```bash
set +e; make dev; rc=$?; echo "rc=$rc"   # Ctrl-C stops both children; rc is the target's own
```

The dev target starts uvicorn and vite as the two children of one foreground recipe and traps their exit, so Ctrl-C stops both and the target cannot silently mean "frontend only". Pass `BACKEND_PORT`/`FRONTEND_PORT` to run a second checkout beside a first one (`make dev BACKEND_PORT=8011 FRONTEND_PORT=5199`); the vite `/api` proxy follows `BACKEND_PORT` through `VITE_API_TARGET`.

Or in two terminals:

```bash
cd backend && .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0
cd frontend && npm run dev -- --host
```

Seed

```bash
set +e; make seed; rc=$?; echo "rc=$rc"
```

Test

```bash
make test
```

Or separately:

```bash
cd backend && .venv/bin/python -m pytest -q
cd frontend && npm run test -- --run
```

`--run` is not optional on the frontend: `npm run test` there is bare vitest, i.e. watch mode, and never exits. `make test-frontend` and the root `npm run test:frontend` both pass `--run` for you.

Lint and format

```bash
make lint
make format
```

### Exit codes and pipes

Documented make invocations are run bare and their exit code is asserted directly (`cmd > /tmp/tq-run.log 2>&1; echo "rc=$?"`). Wrapping one in a pipe to `head` or `tail` is a documentation bug: the pipe reports the consumer's status, so a red target looks green. The same rule covers the manual equivalents below and in `_docs/commands.md`.

```bash
# a documented check: the target runs bare, its rc is captured, the log is read afterwards
set +e
make seed > /tmp/tq-seed.log 2>&1
seed_rc=$?
echo "rc=$seed_rc"   # rc=0 is the pass marker
grep 'seed:' /tmp/tq-seed.log
```

### Interpreter resolution

A backend target picks its interpreter in this order and then fails loudly rather than with a shell "not found": `$BACKEND_PY` (explicit override, e.g. `make seed BACKEND_PY=$PWD/backend/.venv/bin/python`), `backend/.venv/bin/python`, repo-root `.venv/bin/python`, then uv itself - the target syncs `backend/.venv` once and execs from it, so uv is never re-resolved per command. The repo root comes from the Makefile's own location, so the targets work in a tarball copy as well as in a git checkout.

## Development

### Access

Frontend: http://localhost:5173

Backend: http://localhost:8000

API docs: http://localhost:8000/docs

Health: http://localhost:8000/health

### Demo URLs

Join: http://localhost:5173/join?branch=1

Status: http://localhost:5173/status/A001

Lookup: http://localhost:5173/lookup

Board: http://localhost:5173/board/1

Staff login: http://localhost:5173/staff/login (PIN: the `STAFF_PIN` value from backend/.env)

Staff waitlist: http://localhost:5173/staff/waitlist

Staff tables: http://localhost:5173/staff/tables

Settings: http://localhost:5173/admin/settings

### Mobile Testing

Start with --host to bind to 0.0.0.0. Find your local IP (ipconfig / ifconfig) and open http://<your-ip>:5173/join?branch=1 on your phone. Phone and computer must be on the same Wi-Fi.

Add your local IP to CORS_ORIGINS in backend/.env.

### Makefile Targets

Targets run from the repo root and report their own exit code (rc=0 on success, as asserted above). Prefix the
first column with `make` to invoke it; nothing here is piped, so the rc you read is the target's:

setup	Install backend and frontend deps
dev	Run backend and frontend together
backend	Run backend only
frontend	Run frontend only
seed	Reset and seed database
test	Run all tests
test-backend	Run backend tests
test-frontend	Run frontend tests (vitest --run)
lint	Lint backend and frontend
format	Format backend and frontend

## Environment Variables

Backend (backend/.env)
Variable	Default	Required	Description
DATABASE_URL	sqlite:///./dev.db	yes	DB connection
JWT_SECRET	(none - generate one)	yes	JWT signing secret
JWT_EXPIRE_HOURS	12	no	JWT expiry
STAFF_PIN	(none - set one)	yes	One-time seed for the staff credential (T9/D-1)
DEFAULT_BRANCH_ID	1	no	Default branch
CORS_ORIGINS	http://localhost:5173	no	Allowed origins
ENV	(none - required)	yes	Deployment environment. Required, no default: the process refuses to boot unless ENV names one of development, test or production. The development label alone also arms the development-only reset endpoint, so an unset or invented value is never a state the process can fall back to.

Frontend (frontend/.env)
Variable	Default	Description
VITE_API_BASE_URL	/api/v1	API base path
VITE_USE_MOCK	true	Use mock API
VITE_BRANCH_ID	1	Default branch
VITE_ENABLE_SOUND	true	Enable sound
VITE_PUBLIC_BASE_URL	``	Public base URL

`STAFF_PIN` is the single shared staff credential in v1. It has no default and no example value on
purpose: the app refuses to start without it, and on the first boot it is hashed once with bcrypt and
written to the settings row, after which the stored hash is the ONLY credential - the environment
value is a one-time seed, never an accepted login, so rotating the PIN with `POST
/api/v1/auth/change-pin` is the only way to change it and no document here needs to print it.

`JWT_SECRET` has no default and no example value, on purpose: HS256 makes that string the only
credential between an anonymous caller and every staff and admin route, so the app refuses to start
without one that is at least 32 characters long. Generate it and paste the output into backend/.env:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy .env.example to .env in both backend/ and frontend/, and see "One-time local configuration" above for the two backend values that have no printable example.

## Demo

See _docs/demo.md for the full walkthrough.

Quick demo, from a tree you already bootstrapped and seeded above (Getting Started documents both steps with an rc assertion, and re-seeding drops the stored staff credential hash so the `STAFF_PIN` in backend/.env seeds once more):

seed, then open the pages below

Open http://localhost:5173/join?branch=1 and join

Open http://localhost:5173/staff/login with the `STAFF_PIN` value you set above

Both servers come from the dev target above (backend http://localhost:8000, frontend http://localhost:5173); its rc is asserted where it is documented.

## Documentation

- _docs/specs.md — Full specification

- _docs/ui.md — UI guide

- _docs/openapi.yaml — API contract

- _docs/testing.md — Testing guide

- _docs/deployment.md — Deployment guide

- _docs/api-examples.md — curl examples

- _docs/demo.md — Demo script

## Known Limitations

- SQLite concurrent writes limited

- Single worker rate limit

- No Alembic

- No CI

- No production deployment in v1

- No structured logging

- No audit log

- No multi-branch UI

- No external notifications

- No reports page

- No dark mode

- No i18n

- No E2E tests

- No concurrency tests

- No optimistic locking

- No soft delete for waitlist entries

- No status change history

## License

Private project. All rights reserved.
