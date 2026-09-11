# Project Guide

`AGENTS.md` used to carry 17 sections of project content (422 lines). Platform Issue 51 (D-05)
slimmed it to five hard rules and five pointers, and moved the `make` command table to
`_docs/commands.md`. Nothing was deleted: this file is the surviving home for that content, in two
halves.

1. Content map (below): one row per old `AGENTS.md` section, naming where its facts live now.
2. Frozen archive, delimited by the archive marker lines: the old `AGENTS.md`, byte-for-byte, appended with
   `git show HEAD:AGENTS.md`. It is never edited - the headings and numbering stay exactly as they
   were, so citations like `AGENTS.md#5-project-structure` still resolve to a real heading here.

Read this file when you need project rules: the root `AGENTS.md` no longer holds them. Every role
reaches this guide through `_docs/documents.md`, the documents index.

Provenance of the archive: `git show HEAD:AGENTS.md` on the D-05 base commit `583c4ae`, recorded as
archive-sha256: 43fbf4cf2009a2772bb227c12dfbdf3abde94e5ad00ca01efc1cd1d4284f33ce

## Content map

| Old AGENTS.md section | Where the facts live now | Notes |
|---|---|---|
| AGENTS.md section 1 | `_docs/requirements.md`, `_docs/specs.md` | What the project is: guest/staff/admin surfaces, single-store MVP, public board. |
| AGENTS.md section 2 | `_docs/requirements.md` section 2, `_docs/specs.md` | Tech stack table; manifests `backend/pyproject.toml` and `frontend/package.json` are authoritative. |
| AGENTS.md section 3 | `_docs/documents.md`, `_docs/team/roles.md` | Which documents and role files to read; `_docs/requirements.md` section 3 is the original list. |
| AGENTS.md section 4 | `_docs/rules.md`, `_docs/requirements.md` section 4, root `AGENTS.md` | Repo-wide rules 1-5 are now root `AGENTS.md`; project rules 6-15 stay in `_docs/requirements.md` section 4. |
| AGENTS.md section 5 | `_docs/requirements.md` section 5, `_docs/specs.md` | Project Structure tree; cited as `AGENTS.md#5-project-structure` by `_docs/plan.md` (redirect row F-02). |
| AGENTS.md section 6 | `_docs/commands.md` | The make-target table moved there verbatim; `_docs/testing.md` section 8 owns test commands. |
| AGENTS.md section 7 | `_docs/requirements.md` section 7, `_docs/specs.md`, `_docs/testing.md` | Backend Guidelines: routers/services/models/schemas/errors/dependencies, UTC, `AppError`; cited as `AGENTS.md#7-backend-guidelines` (redirect row F-04). |
| AGENTS.md section 8 | `_docs/requirements.md` section 8, `_docs/ui.md`, `_docs/testing.md` | Frontend Guidelines: api/stores/layouts/pages/components/hooks/lib, polling and query keys; cited as `AGENTS.md#8-frontend-guidelines` (redirect row F-06). |
| AGENTS.md section 9 | `_docs/ui.md`, `_docs/design-system.md`, `_docs/specs.md` | UI Rules pointer map; `_docs/ui.md` wins on any conflict. |
| AGENTS.md section 10 | `_docs/specs.md` section 5 | State machine: 6 waitlist and 3 table states; 15 waitlist transition rows and 4 table transition rows in the two `Allowed transitions` / `Table transitions` tables of `_docs/specs.md` section 5. |
| AGENTS.md section 11 | `_docs/specs.md` section 13 | Time and timezone: store UTC, display `Asia/Taipei`, `business_date` cutoff. |
| AGENTS.md section 12 | `_docs/specs.md` section 8 | Queue number: `seq`, `A001` display, `A-20260910-001` full form, daily reset. |
| AGENTS.md section 13 | `_docs/specs.md` section 11, `_docs/openapi.yaml` | Error codes and the `error.code/message/details` shape; `_docs/api-examples.md` shows rendered payloads. |
| AGENTS.md section 14 | `_docs/testing.md`, `_docs/testing-guidelines.md`, `_docs/commands.md` | Testing strategy and runners. |
| AGENTS.md section 15 | `_docs/requirements.md` section 15 | Do Not Do list (14 rows). |
| AGENTS.md section 16 | `_docs/requirements.md` section 16, `_docs/rules.md` | If Stuck escalation ladder; unclear rule means BLOCKER, never a guess. |
| AGENTS.md section 17 | `CONTRIBUTING.md`, `_docs/documents.md` | File Ownership table and its recorded divergences. |

## Redirect rows for the open citations

| Citing artifact | Cites | Resolves to |
|---|---|---|
| F-02 (`_docs/issues/F-02.md`, Platform #13) | `AGENTS.md#5-project-structure` | AGENTS.md section 5 in the archive below, plus `_docs/requirements.md` section 5 |
| F-04 (`_docs/issues/F-04.md`, Platform #15) | `AGENTS.md#7-backend-guidelines` | AGENTS.md section 7 in the archive below, plus `_docs/requirements.md` section 7 |
| F-06 (`_docs/issues/F-06.md`, Platform #17) | `AGENTS.md#8-frontend-guidelines` | AGENTS.md section 8 in the archive below, plus `_docs/requirements.md` section 8 |
| `_docs/plan.md` (Platform #11) | Project Structure, Backend Guidelines, Frontend Guidelines anchors (9 citations) | The three archive headings, unchanged; the anchor text keeps its numbering |
| `README.md`, `CONTRIBUTING.md` | `AGENTS.md` sections generally | This guide: content map plus the frozen archive |

<!-- BEGIN-ARCHIVE -->
# AGENTS

## 1. What This Project Is

TableQueue is a restaurant waitlist manager.

- Guest side: join waitlist, view status, cancel.
- Staff side: call, seat, no-show, restore, revert, cancel, edit, reorder, manage tables, dashboard.
- Admin side: store info, waitlist settings, tables CRUD, change PIN, reset data (dev only).
- Public board: read-only, shows current call, next up, recent calls, waiting count, QR code.

Single-store MVP, but the data model keeps `restaurant_id` and `branch_id` for future expansion.
This file is the route map, not the spec: the pages named under `Read These Files First` carry the
detail, and the 17 section headings below are the stable anchors that `_docs/plan.md` cites.

## 2. Tech Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, uv, SQLAlchemy 2.0, Pydantic v2, SQLite |
| Frontend | React 18, Vite, TypeScript, Tailwind, shadcn/ui, TanStack Query, Zustand |
| Auth | Single shared PIN, then JWT |
| Testing | pytest (backend), Vitest + RTL (frontend) |
| Tooling | Makefile, concurrently, ruff, eslint, prettier |

Authority: `_docs/requirements.md` section 2. This file deliberately does not restate dependency
versions or the install matrix: `_docs/requirements.md` section 2 and the manifests
(`backend/pyproject.toml`, `frontend/package.json`) are the source of truth.

## 3. Read These Files First

The Orchestrator passes the role file path; a subagent reads `AGENTS.md` plus that one role file and
nothing else. Before starting any task, read:

1. Your role file: `_docs/team/orchestrator.md`, `_docs/team/sa.md`, `_docs/team/pm.md`,
   `_docs/team/sw.md`, `_docs/team/qa.md` (passed by the Orchestrator)
2. `AGENTS.md` (this file)
3. `_docs/specs.md` — full specification
4. `_docs/ui.md` — UI guide
5. `_docs/openapi.yaml` — API contract
6. `_docs/testing.md` — testing guide
7. `CONTRIBUTING.md` — issue and PR workflow

If a task references a specific section, read that section. Task-specific authority: the AC blocks
and constraints in `_docs/issues/<ID>.md` (what to build is never inferred from this guide), then
`_docs/openapi.yaml` for response shapes and `_docs/specs.md` for behaviour; where an issue file
disagrees with either, the contract wins and the disagreement goes in the PR description.

## 4. Hard Rules

### Repo-wide rules (apply to ALL roles)

1. Read your role file before doing anything. Role files live in `_docs/team/`.
2. Do NOT perform other roles' work.
3. Always declare `reached_state` in output.
4. Never skip your Pre-output checklist.
5. If a rule is unclear: post BLOCKER, do not guess.

### Project rules (from `_docs/requirements.md` section 4)

6. **All UI text must be in English.** No CJK characters in user-visible strings.
7. **Date format**: `2026-09-10 21:00` (ISO + 24h).
8. **Phone format**: Taiwan `09xx-xxx-xxx` / `02-xxxx-xxxx`.
9. **Do not add features** not listed in `_docs/specs.md`.
10. **Do not modify `_docs/specs.md`** without an explicit docs issue.
11. **Follow `_docs/openapi.yaml` exactly** for all API shapes.
12. **One issue at a time.** Do not batch.
13. **Do not commit** `.env`, `dev.db`, `node_modules`, `__pycache__`, `dist`.
14. **Run tests before marking done.**
15. **If spec is unclear, stop and ask.** Do not guess.

## 5. Project Structure

```
table-queue/
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── dependencies.py
│   │   ├── errors.py
│   │   ├── routers/
│   │   │   ├── public.py
│   │   │   ├── staff.py
│   │   │   ├── admin.py
│   │   │   └── auth.py
│   │   ├── services/
│   │   │   ├── waitlist.py
│   │   │   ├── tables.py
│   │   │   └── settings.py
│   │   └── seed.py
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── .env.example
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── routes.ts
│       ├── api/
│       ├── stores/
│       ├── layouts/
│       ├── pages/
│       ├── components/
│       ├── hooks/
│       └── lib/
├── _docs/
│   ├── specs.md
│   ├── ui.md
│   ├── testing.md
│   ├── deployment.md
│   ├── openapi.yaml
│   ├── api-examples.md
│   ├── demo.md
│   └── issues/
├── Makefile
├── package.json
├── README.md
├── CONTRIBUTING.md
├── AGENTS.md
├── .editorconfig
├── .gitignore
└── .nvmrc
```

The anchor `AGENTS.md#5-project-structure` matches the citation at `_docs/plan.md:1921`. Every path
in this tree now exists; the checkout is authoritative over this list, so if the two disagree, fix
this section through a docs issue rather than coding around the guide.

## 6. Commands

The commands below all run in this checkout today: `Makefile`, `backend/`, `frontend/` and the root
`package.json` were created by Platform Issue 12 (F-01, closed). Run them from the repo root.

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

## 7. Backend Guidelines

Structure (from `_docs/requirements.md` section 7):

1. **routers/** — FastAPI routers, no SQL.
2. **services/** — business logic, no HTTP.
3. **models.py** — SQLAlchemy 2.0 models with `Mapped[]` and `mapped_column()`.
4. **schemas.py** — Pydantic v2 request/response, separate classes per direction.
5. **errors.py** — `AppError` and exception handlers.
6. **dependencies.py** — `get_db`, `get_current_staff`, `get_now`.

Rules: SQLAlchemy 2.0 style; Pydantic v2; all timestamps stored in UTC; never call
`datetime.utcnow()` inside models, inject `now`; every write endpoint wraps a transaction; errors
raise `AppError` with a code from `_docs/specs.md` section 11; never log phone, name, or token;
never expose `staff_pin_hash`.

Error handling: services raise `AppError(code, status_code, details)`; routers do not catch, the
global handler renders JSON; validation errors go through the FastAPI `RequestValidationError`
handler; unhandled exceptions return `INTERNAL_ERROR` with no stack trace.

Testing: write the test first; in-memory SQLite; freezegun for time; cover success and failure and
every state-machine transition. Authority: `_docs/specs.md` section 11 for error shapes,
`_docs/testing.md` section 2 for backend test strategy.

## 8. Frontend Guidelines

Structure (from `_docs/requirements.md` section 8):

1. **api/** — the only place that talks to the backend.
2. **stores/** — Zustand for UI state only.
3. **layouts/** — `PublicLayout`, `StaffLayout`.
4. **pages/** — route components.
5. **components/** — reusable components; `components/ui/` is shadcn/ui generated code only.
6. **hooks/** — TanStack Query hooks and custom hooks.
7. **lib/** — helpers: `format.ts`, `publicBaseUrl.ts`, `strings.ts`.

Rules: every backend call goes through `api/client.ts`; never fetch directly in components;
TanStack Query owns server state, Zustand owns UI state only; refetch on window focus and
immediately when a countdown reaches 0; all UI text in English; skeletons for loading (not
spinners); toasts for transient errors; inline errors for form fields; `ConfirmDialog` for
destructive actions; respect `prefers-reduced-motion`; every icon button carries an `aria-label`.

Polling intervals are a product rule owned by `_docs/requirements.md` section 8 and the
per-page specs in `_docs/ui.md` section 6, not by this file: staff waitlist 3 seconds, tables 5
seconds, guest status 5 seconds, board 5 seconds, settings no polling.

Naming: components PascalCase, hooks `useCamelCase`, files match the export name, other files
camelCase or kebab-case.

Styling: Tailwind plus shadcn/ui. Guest surfaces are warm, spacious, `rounded-2xl`, `max-w-md`;
staff surfaces are dense, colour-coded, `rounded-lg`, `max-w-7xl`. No dark mode in v1. Use the
status colour tokens defined in `_docs/ui.md`.

Forms: `react-hook-form` plus zod; validate on blur, re-validate on change; disable submit while
pending; field errors below fields; keep form values on error.

Query keys are centralised in `api/queryKeys.ts`: `waitlist(branchId)`,
`waitlistStatus(branchId, queueNumber)`, `tables(branchId)`, `dashboard(branchId)`,
`settings(branchId)`, `publicBranch(branchId)`, `board(branchId)`.

`api/client.ts` handles: base URL from `VITE_API_BASE_URL`, the Authorization header from
`staffStore.token`, a 30s timeout with `AbortController`, 401 (clear token, clear query cache,
redirect to login), 429 (toast), 5xx (toast), and a network failure that never reached the backend
as `NETWORK_ERROR`. `api/errors.ts` maps error codes to English messages. `api/mock/` provides mock
responses controlled by `VITE_USE_MOCK`, and mock data must match `_docs/openapi.yaml` and seed data.

Authority: `_docs/testing.md` section 3 for test strategy, `_docs/ui.md` for tokens, per-page
layout and copy.

## 9. UI Rules

**`_docs/ui.md` is the single source of truth** for design tokens, typography, the component
inventory, page layouts, states, responsive rules and accessibility. This section is the pointer
map; `_docs/design-system.md` explains how those rules are wired into the code. Neither page is
restated here: where a rule and this summary disagree, `_docs/ui.md` wins.

| Topic | Source of truth |
|---|---|
| Design principles, colour tokens, typography, spacing and radius | `_docs/ui.md` sections 1-4 |
| Component inventory (shadcn/ui and custom), button sizes and states | `_docs/ui.md` section 5 |
| Per-page layout and behaviour | `_docs/ui.md` section 6 |
| Empty / loading / error states | `_docs/ui.md` sections 7-9 |
| Responsive breakpoints and layout rules | `_docs/ui.md` section 10 |
| Accessibility rules | `_docs/ui.md` section 11 |
| Motion, sounds, icons | `_docs/ui.md` sections 12-14 |
| Confirm dialogs and toasts | `_docs/ui.md` sections 15-16 |
| Custom component props | `_docs/ui.md` section 19 |
| Business rules behind the UI | `_docs/specs.md` |
| API shapes the UI consumes | `_docs/openapi.yaml` |

Wiring, component conventions, state rendering, responsive and accessibility rules, copy rules and
theme are summarised in `_docs/design-system.md` sections 1 to 8, which cite `_docs/ui.md` for every
value. Three rules are hard enough to state here: no hex colour literal appears in a `.tsx` file (a
missing token is added to `_docs/ui.md` first, then to `tailwind.config.js`); a component that
appears in a page mock-up but not in `_docs/ui.md` section 5 is not built until a docs issue extends
`_docs/ui.md`; every screen renders four states - loading, empty, error, data (`_docs/design-system.md`
section 5). Light theme only in v1; dark mode and i18n are non-goals (`_docs/ui.md` sections 17-18).

## 10. State Machine

Summarised from `_docs/specs.md` section 5, which is the authoritative source with all 23 transition
rules and the dash-item state lines.

Waitlist states (6 states):

| From | To | Trigger |
|---|---|---|
| `WAITING` | `CALLED` | Call |
| `WAITING` | `SEATED` | Seat |
| `WAITING` | `CANCELLED` | Cancel |
| `CALLED` | `SEATED` | Seat |
| `CALLED` | `NO_SHOW` | No-show or timeout |
| `CALLED` | `WAITING` | Revert |
| `CALLED` | `CANCELLED` | Cancel with confirm |
| `SEATED` | `DONE` | Release table |
| `SEATED` | `CANCELLED` | Staff cancel |
| `NO_SHOW` | `WAITING` | Restore |
| `CANCELLED` | — | terminal |
| `DONE` | — | terminal |

Table states (3 states): `AVAILABLE` ↔ `CLEANING` (manual), `AVAILABLE` → `OCCUPIED` (seat),
`OCCUPIED` → `AVAILABLE` (release).

Rules: `OCCUPIED` cannot be set directly via `PATCH /staff/tables/{id}`; the `CALLED` timeout uses
`hold_minutes_snapshot`; lazy no-show evaluates on read; releasing a table sets the entry to `DONE`;
cancel releases the table if any; closing the day closes all active entries.

## 11. Time and Timezone

Summarised from `_docs/specs.md` section 13.

- Store UTC.
- Display `Asia/Taipei`.
- Date format: `2026-09-10`.
- DateTime format: `2026-09-10 21:00`.
- `business_date` uses the branch timezone and cutoff hour (default 4).
- `remaining_seconds` is returned by the backend for `CALLED` entries.
- The frontend does not compute time differences.

## 12. Queue Number

Summarised from `_docs/specs.md` section 8.

- `seq` = max seq for `(branch_id, business_date, queue_prefix)` + 1.
- `queue_number` display: `A001`.
- `full_queue_number` unique: `A-20260910-001`.
- Resets daily.
- Not unique across days.
- Guest lookup without a token only searches the current `business_date`.

## 13. Errors

Summarised from `_docs/specs.md` section 11, which owns this table. All errors use the shape:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": {}
  }
}
```

| Code | HTTP | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Field validation failed |
| `WAITLIST_DUPLICATE_PHONE` | 409 | Phone already on active waitlist |
| `WAITLIST_NOT_FOUND` | 404 | Waitlist entry not found |
| `WAITLIST_INVALID_STATUS` | 409 | Action not allowed for current status |
| `WAITLIST_CLOSED` | 409 | Waitlist is paused |
| `AUTH_INVALID_PIN` | 401 | PIN incorrect |
| `AUTH_TOKEN_EXPIRED` | 401 | JWT expired or invalid |
| `TABLE_NOT_FOUND` | 404 | Table not found |
| `TABLE_NOT_AVAILABLE` | 409 | Table not available |
| `CONFLICT` | 409 | Conflict with another change |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Unhandled error |
| `BRANCH_NOT_FOUND` | 404 | Branch not found |

Codes are listed alphabetically, matching `_docs/specs.md` section 11; no code is defined here that
the spec does not list.

### Frontend-only code

- `NETWORK_ERROR` — synthesised client-side by the API client when a request never reaches the
  backend (`_docs/specs.md` section 11, `_docs/testing.md` section 3).

The frontend maps codes to English messages in `api/errors.ts`.

## 14. Testing

```bash
make test          # both suites
cd backend && uv run pytest     # backend only
cd frontend && npm run test     # frontend only
```

Commands authority: `_docs/testing.md` section 8. No test command was available in this checkout
until Platform Issue 12 created `Makefile`, `backend/` and `frontend/`; that issue is closed, so
failing to find a runner today is a defect in the repo, not a documentation gap.
## 15. Do Not Do

From `_docs/requirements.md` section 15:

1. Do not add features not in `_docs/specs.md`.
2. Do not modify `_docs/specs.md` without a docs issue.
3. Do not use `transition-all`.
4. Do not use spinners for page loading.
5. Do not log phone, name, or token.
6. Do not expose `staff_pin_hash`.
7. Do not use camelCase in JSON responses.
8. Do not use `datetime.utcnow()`.
9. Do not call `Date.now()` inside components without injection.
10. Do not fetch directly in components.
11. Do not use `localStorage` for anything except `staffStore`.
12. Do not commit `.env`, `dev.db`, `node_modules`, `__pycache__`, `dist`.
13. Do not batch multiple issues into one branch.
14. Do not guess when spec is unclear.

## 16. If Stuck

From `_docs/requirements.md` section 16:

1. Re-read `_docs/specs.md` and `_docs/openapi.yaml`.
2. Check `_docs/testing.md` for expected behavior.
3. Check `_docs/demo.md` for end-to-end flow.
4. If still unclear, stop and ask in the issue or PR.
5. Do not guess.

## 17. File Ownership

Same 13 rows as `CONTRIBUTING.md` `## File Ownership` (Platform #9, closed); `_docs/documents.md`
wins on role reachability where sources conflict.

| Path | Owner |
|---|---|
| `_docs/specs.md` | PM |
| `_docs/ui.md` | PM |
| `_docs/openapi.yaml` | PM + backend |
| `_docs/testing.md` | PM + both |
| `_docs/deployment.md` | PM |
| `_docs/issues/` | PM |
| `backend/` | backend |
| `frontend/` | frontend |
| `README.md` | PM |
| `CONTRIBUTING.md` | PM |
| `AGENTS.md` | PM |
| `Makefile` | both |
| `root package.json` | both |

Two paths are not listed in either table because they were created after Platform #9 closed:
`_docs/requirements.md`, owned by PM and read by SA (it is the source this guide summarises), and
`_docs/orchestrator-playbook.md`, owned by the Orchestrator (hard-won operating knowledge: contract
precedence, how to write ACs that cannot lie, and the traps this stack and harness actually enforce).
Extending a File Ownership table is a docs-issue edit to `CONTRIBUTING.md`, not a silent addition
here.

### Recorded divergences

1. `_docs/documents.md` lists the agent guide as `_docs/AGENTS.md`, a path that does not exist; the
   real file is root `AGENTS.md`. **No owning issue exists** for `_docs/documents.md`.
2. `_docs/documents.md` grants SA and SW write or read access to `_docs/design-system.md`; that file
   exists and is read-only reference. **No owning issue exists**.
3. `_docs/plan.md:1921` cites `AGENTS.md#5-project-structure` while this file's headings are
   numbered (recorded as Platform Issue 11); the anchor is kept by numbering.
<!-- END-ARCHIVE -->
