# TableQueue — Agent Guide

Version: 0.1.0
Last updated: 2026-09-10

This file is read first by any coding agent working on this repo.
Read it fully before touching any code.

---

## 1. What This Project Is

TableQueue is a restaurant waitlist manager.

- Guest side: join waitlist, view status, cancel.
- Staff side: call, seat, no-show, restore, revert, cancel, edit, reorder, manage tables, dashboard.
- Admin side: store info, waitlist settings, tables CRUD, change PIN, reset data (dev only).
- Public board: read-only, shows current call, next up, recent calls, waiting count, QR code.

Single-store MVP, but data model keeps `restaurant_id` and `branch_id` for future expansion.

---

## 2. Tech Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, uv, SQLAlchemy 2.0, Pydantic v2, SQLite |
| Frontend | React 18, Vite, TypeScript, Tailwind, shadcn/ui, TanStack Query, Zustand |
| Auth | Single shared PIN → JWT |
| Testing | pytest (backend), Vitest + RTL (frontend) |
| Tooling | Makefile, concurrently, ruff, eslint, prettier |

---

## 3. Read These Files First

Before starting any task, read:

1. `AGENTS.md` (this file)
2. `_docs/specs.md` — full specification
3. `_docs/ui.md` — UI guide
4. `_docs/openapi.yaml` — API contract
5. `_docs/testing.md` — testing guide
6. `CONTRIBUTING.md` — issue and PR workflow

If a task references a specific section, read that section.

---

## 4. Hard Rules

1. **All UI text must be in English.**
2. **Date format**: `2026-09-10 21:00` (ISO + 24h).
3. **Phone format**: Taiwan `09xx-xxx-xxx` / `02-xxxx-xxxx`.
4. **Do not add features** not listed in `_docs/specs.md`.
5. **Do not modify `_docs/specs.md`** without an explicit docs issue.
6. **Follow `_docs/openapi.yaml` exactly** for all API shapes.
7. **One issue at a time.** Do not batch.
8. **Do not commit** `.env`, `dev.db`, `node_modules`, `__pycache__`, `dist`.
9. **Run tests before marking done.**
10. **If spec is unclear, stop and ask.** Do not guess.

---

## 5. Project Structure

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
│ ├── stores/
│ ├── layouts/
│ ├── pages/
│ ├── components/
│ ├── hooks/
│ └── lib/
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


---

## 6. Commands

### Setup
```bash
make setup
# or:
cd backend && uv sync
cd frontend && npm install
npm install
```

Run
bash
make dev
# or in two terminals:
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0
cd frontend && npm run dev -- --host
Seed
bash
make seed
# or:
cd backend && uv run python -m app.seed --reset
Test
bash
make test
# or:
cd backend && uv run pytest
cd frontend && npm run test
Lint
bash
make lint
# or:
cd frontend && npm run lint
Format
bash
make format
# or:
cd frontend && npm run format
7. Backend Guidelines
Structure
routers/ — FastAPI routers, no SQL.

services/ — business logic, no HTTP.

repositories/ — optional in v1, can be merged into services.

models.py — SQLAlchemy 2.0 models with Mapped[] and mapped_column().

schemas.py — Pydantic v2 request/response.

errors.py — AppError and exception handlers.

dependencies.py — get_db, get_current_staff, get_now.

Rules
Use SQLAlchemy 2.0 style.

Use Pydantic v2.

Request and response schemas are separate classes.

All timestamps stored in UTC.

Never call datetime.utcnow() inside models; inject now.

All write endpoints wrap a transaction.

Errors use AppError with code from _docs/specs.md.

Never log phone, name, or token.

Never expose staff_pin_hash.

Error Handling
Raise AppError(code, status_code, details) in services.

Routers do not catch; global handler converts to JSON.

Validation errors use FastAPI RequestValidationError handler.

Unhandled exceptions return INTERNAL_ERROR without stack trace.

Testing
Write tests first, then implement.

Use in-memory SQLite.

Use freezegun for time.

Cover success and failure cases.

Cover state machine transitions.

8. Frontend Guidelines
Structure
api/ — the only place that talks to the backend.

stores/ — Zustand for UI state only.

layouts/ — PublicLayout, StaffLayout.

pages/ — route components.

components/ — reusable components.

components/ui/ — shadcn/ui generated components only.

hooks/ — TanStack Query hooks and custom hooks.

lib/ — helpers: format.ts, publicBaseUrl.ts, strings.ts.

Rules
All backend calls go through api/client.ts.

Never fetch directly in components.

Use TanStack Query for server state.

Use Zustand for UI state only.

Polling intervals:

Staff waitlist: 3 seconds

Tables: 5 seconds

Guest status: 5 seconds

Board: 5 seconds

Settings: no polling

Refetch on window focus.

Refetch immediately when countdown reaches 0.

All UI text in English.

Use skeletons for loading, not spinners.

Use toasts for transient errors.

Use inline errors for form fields.

Use ConfirmDialog for destructive actions.

Respect prefers-reduced-motion.

All icon buttons have aria-label.

Naming
Components: PascalCase.

Hooks: useCamelCase.

Files: match export name.

Other files: camelCase or kebab-case.

Styling
Tailwind + shadcn/ui.

Guest side: warm, spacious, rounded-2xl, max-w-md.

Staff side: dense, color-coded, rounded-lg, max-w-7xl.

No dark mode in v1.

Use status color tokens from _docs/ui.md.

Forms
react-hook-form + zod.

Validate on blur, re-validate on change.

Disable submit while pending.

Show field errors below fields.

Keep form values on error.

Query Keys
Centralized in api/queryKeys.ts:

waitlist(branchId)

waitlistStatus(branchId, queueNumber)

tables(branchId)

dashboard(branchId)

settings(branchId)

publicBranch(branchId)

board(branchId)

API Client
api/client.ts handles:

Base URL from VITE_API_BASE_URL

Authorization header from staffStore.token

30s timeout with AbortController

401 → clear token, clear query cache, redirect to login

429 → toast

5xx → toast

Network error → NETWORK_ERROR

api/errors.ts maps error codes to English messages.

Mock
api/mock/ provides mock responses.

Controlled by VITE_USE_MOCK.

Mock data must match _docs/openapi.yaml and seed data.

9. UI Rules
Guest Side
Mobile-first.

Large text for queue number (text-5xl).

Rounded corners (rounded-2xl).

Soft shadows (shadow-sm).

Warm background (#FFFBF5).

Status colors from _docs/ui.md.

Progress bar: Waiting → Called → Seated.

Countdown on CALLED.

Sound toggle.

Cancel with confirmation on CALLED.

Staff Side
Tablet/desktop-first.

Dense information.

Cool background (#F8FAFC).

Color-coded statuses.

Stats cards at top.

Search, filter, pause switch.

Collapsible closed section.

Last updated timestamp.

Confirm destructive actions.

Public Board
Read-only.

No auth.

Shows restaurant name, branch, hours.

Shows current call, next up, recent calls.

Shows waiting count.

QR code for join.

Never shows names or phones.

Polls every 5 seconds.

10. State Machine
Waitlist
WAITING → CALLED (Call)

WAITING → SEATED (Seat)

WAITING → CANCELLED (Cancel)

CALLED → SEATED (Seat)

CALLED → NO_SHOW (No-show or timeout)

CALLED → WAITING (Revert)

CALLED → CANCELLED (Cancel with confirm)

SEATED → DONE (Release table)

SEATED → CANCELLED (Staff cancel)

NO_SHOW → WAITING (Restore)

CANCELLED → terminal

DONE → terminal

Table
AVAILABLE ↔ CLEANING (manual)

AVAILABLE → OCCUPIED (seat)

OCCUPIED → AVAILABLE (release)

Rules
OCCUPIED cannot be set directly via PATCH /staff/tables/{id}.

CALLED timeout uses hold_minutes_snapshot.

Lazy no-show evaluated on read.

Release table sets entry to DONE.

Cancel releases table if any.

Close day closes all active entries.

11. Time and Timezone
Store UTC.

Display Asia/Taipei.

Date format: 2026-09-10.

DateTime format: 2026-09-10 21:00.

business_date uses branch timezone and cutoff hour (default 4).

remaining_seconds returned by backend for CALLED entries.

Frontend does not compute time differences.

12. Queue Number
seq = max seq for (branch_id, business_date, queue_prefix) + 1.

queue_number display: A001.

full_queue_number unique: A-20260910-001.

Resets daily.

Not unique across days.

Guest lookup without token only searches current business_date.


13. Errors
All errors use:

json
{
  "error": {
    "code": "WAITLIST_NOT_FOUND",
    "message": "Waitlist entry not found",
    "details": {}
  }
}
Codes:

VALIDATION_ERROR

WAITLIST_DUPLICATE_PHONE

WAITLIST_NOT_FOUND

WAITLIST_INVALID_STATUS

WAITLIST_CLOSED

AUTH_INVALID_PIN

AUTH_TOKEN_EXPIRED

AUTH_RATE_LIMITED

TABLE_NOT_FOUND

TABLE_NOT_AVAILABLE

SETTINGS_NOT_FOUND

CONFLICT

RATE_LIMITED

INTERNAL_ERROR

BRANCH_NOT_FOUND

NETWORK_ERROR (frontend only)

Frontend maps codes to English messages in api/errors.ts.

14. Testing
Backend: uv run pytest

Frontend: npm run test

Both: make test

See _docs/testing.md for full strategy.

15. Do Not Do
Do not add features not in _docs/specs.md.

Do not modify _docs/specs.md without a docs issue.

Do not use transition-all.

Do not use spinners for page loading.

Do not log phone, name, or token.

Do not expose staff_pin_hash.

Do not use camelCase in JSON responses.

Do not use datetime.utcnow().

Do not call Date.now() inside components without injection.

Do not fetch directly in components.

Do not use localStorage for anything except staffStore.

Do not commit .env, dev.db, node_modules, __pycache__, dist.

Do not batch multiple issues into one branch.

Do not guess when spec is unclear.

16. If Stuck
Re-read _docs/specs.md and _docs/openapi.yaml.

Check _docs/testing.md for expected behavior.

Check _docs/demo.md for end-to-end flow.

If still unclear, stop and ask in the issue or PR.

Do not guess.

17. File Ownership
Path	Owner
_docs/specs.md	PM
_docs/ui.md	PM
_docs/openapi.yaml	PM + backend
_docs/testing.md	PM + both
_docs/deployment.md	PM
_docs/issues/	PM
backend/	backend
frontend/	frontend
README.md	PM
CONTRIBUTING.md	PM
AGENTS.md	PM
Makefile	both
root package.json	both