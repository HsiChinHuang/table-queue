# AGENTS

## 1. What This Project Is

TableQueue is a restaurant waitlist manager.

- Guest side: join waitlist, view status, cancel.
- Staff side: call, seat, no-show, restore, revert, cancel, edit, reorder, manage tables, dashboard.
- Admin side: store info, waitlist settings, tables CRUD, change PIN, reset data (dev only).
- Public board: read-only, shows current call, next up, recent calls, waiting count, QR code.

Single-store MVP, but data model keeps `restaurant_id` and `branch_id` for future expansion.

## 2. Tech Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, uv, SQLAlchemy 2.0, Pydantic v2, SQLite |
| Frontend | React 18, Vite, TypeScript, Tailwind, shadcn/ui, TanStack Query, Zustand |
| Auth | Single shared PIN → JWT |
| Testing | pytest (backend), Vitest + RTL (frontend) |
| Tooling | Makefile, concurrently, ruff, eslint, prettier |

Authority: `_docs/requirements.md` section 2. Any disagreement with `README.md` (Platform Issue 8) is recorded in Out of scope, never fixed here.

## 3. Read These Files First

The Orchestrator passes the role file path; the subagent reads it plus `AGENTS.md`. Before starting any task, read:

1. Your role file: `_docs/team/orchestrator.md`, `_docs/team/sa.md`, `_docs/team/pm.md`, `_docs/team/sw.md`, `_docs/team/qa.md` (passed by Orchestrator)
2. `AGENTS.md` (this file)
3. `_docs/specs.md` — full specification
4. `_docs/ui.md` — UI guide
5. `_docs/openapi.yaml` — API contract
6. `_docs/testing.md` — testing guide
7. `CONTRIBUTING.md` — issue and PR workflow

If a task references a specific section, read that section.

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

This is the target structure. `backend/`, `frontend/`, `Makefile`, `package.json`, `.editorconfig`, `.gitignore`, `.nvmrc` do not exist in this checkout; they are created by Platform Issue 12 (F-01). The anchor `AGENTS.md#5-project-structure` matches the citation at `_docs/plan.md:1921`.

## 6. Commands

The `Makefile`, `make` targets, `backend/`, `frontend/` and root `package.json` are created by Platform Issue 12 (F-01). None of them exist in this checkout today, so these commands do not run here yet. They are documented for reference.

### Setup (does not exist yet, tracked by Platform Issue 12)

```bash
make setup
# or manually:
cd backend && uv sync
cd frontend && npm install
npm install
```

### Run (does not exist yet, tracked by Platform Issue 12)

```bash
make dev
# or in two terminals:
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0
cd frontend && npm run dev -- --host
```

### Seed (does not exist yet, tracked by Platform Issue 12)

```bash
make seed
# or:
cd backend && uv run python -m app.seed --reset
```

### Test (does not exist yet, tracked by Platform Issue 12)

```bash
make test
# or separately:
cd backend && uv run pytest
cd frontend && npm run test
```

### Lint and Format (does not exist yet, tracked by Platform Issue 12)

```bash
make lint
make format
# or:
cd frontend && npm run lint
cd frontend && npm run format
```

### Makefile Targets (does not exist yet, tracked by Platform Issue 12)

| Target | Description |
|---|---|
| `make setup` | Install backend and frontend deps |
| `make dev` | Run backend and frontend together |
| `make backend` | Run backend only |
| `make frontend` | Run frontend only |
| `make seed` | Reset and seed database |
| `make test` | Run all tests |
| `make test-backend` | Run backend tests |
| `make test-frontend` | Run frontend tests |
| `make lint` | Lint frontend |
| `make format` | Format frontend |

Commands reference: `_docs/requirements.md` section 6, `_docs/testing.md` section 8, `_docs/plan.md` F-01.

## 7. Backend Guidelines

### Structure (from `_docs/requirements.md` section 7)

- `routers/` — FastAPI routers, no SQL.
- `services/` — business logic, no HTTP.
- `models.py` — SQLAlchemy 2.0 models with `Mapped[]` and `mapped_column()`.
- `schemas.py` — Pydantic v2 request/response.
- `errors.py` — `AppError` and exception handlers.
- `dependencies.py` — `get_db`, `get_current_staff`, `get_now`.

### Rules

- Use SQLAlchemy 2.0 style.
- Use Pydantic v2.
- Request and response schemas are separate classes.
- All timestamps stored in UTC.
- Never call `datetime.utcnow()` inside models; inject `now`.
- All write endpoints wrap a transaction.
- Errors use `AppError` with code from `_docs/specs.md`.
- Never log phone, name, or token.
- Never expose `staff_pin_hash`.

### Error Handling

- Raise `AppError(code, status_code, details)` in services.
- Routers do not catch; global handler converts to JSON.
- Validation errors use FastAPI `RequestValidationError` handler.
- Unhandled exceptions return `INTERNAL_ERROR` without stack trace.

### Testing

- Write tests first, then implement.
- Use in-memory SQLite.
- Use freezegun for time.
- Cover success and failure cases.
- Cover state machine transitions.

## 8. Frontend Guidelines

### Structure (from `_docs/requirements.md` section 8)

- `api/` — the only place that talks to the backend.
- `stores/` — Zustand for UI state only.
- `layouts/` — `PublicLayout`, `StaffLayout`.
- `pages/` — route components.
- `components/` — reusable components.
- `components/ui/` — shadcn/ui generated components only.
- `hooks/` — TanStack Query hooks and custom hooks.
- `lib/` — helpers: `format.ts`, `publicBaseUrl.ts`, `strings.ts`.

### Rules

- All backend calls go through `api/client.ts`.
- Never fetch directly in components.
- Use TanStack Query for server state.
- Use Zustand for UI state only.
- Polling intervals:
  - Staff waitlist: 3 seconds
  - Tables: 5 seconds
  - Guest status: 5 seconds
  - Board: 5 seconds
  - Settings: no polling
- Refetch on window focus.
- Refetch immediately when countdown reaches 0.
- All UI text in English.
- Use skeletons for loading, not spinners.
- Use toasts for transient errors.
- Use inline errors for form fields.
- Use `ConfirmDialog` for destructive actions.
- Respect `prefers-reduced-motion`.
- All icon buttons have `aria-label`.

### Naming

- Components: PascalCase.
- Hooks: useCamelCase.
- Files: match export name.
- Other files: camelCase or kebab-case.

### Styling

- Tailwind + shadcn/ui.
- Guest side: warm, spacious, rounded-2xl, max-w-md.
- Staff side: dense, color-coded, rounded-lg, max-w-7xl.
- No dark mode in v1.
- Use status color tokens from `_docs/ui.md`.

### Forms

- `react-hook-form` + zod.
- Validate on blur, re-validate on change.
- Disable submit while pending.
- Show field errors below fields.
- Keep form values on error.

### Query Keys

Centralized in `api/queryKeys.ts`:

- `waitlist(branchId)`
- `waitlistStatus(branchId, queueNumber)`
- `tables(branchId)`
- `dashboard(branchId)`
- `settings(branchId)`
- `publicBranch(branchId)`
- `board(branchId)`

### API Client

`api/client.ts` handles:

- Base URL from `VITE_API_BASE_URL`
- Authorization header from `staffStore.token`
- 30s timeout with `AbortController`
- 401 → clear token, clear query cache, redirect to login
- 429 → toast
- 5xx → toast
- Network error → `NETWORK_ERROR`

`api/errors.ts` maps error codes to English messages.

### Mock

`api/mock/` provides mock responses. Controlled by `VITE_USE_MOCK`. Mock data must match `_docs/openapi.yaml` and seed data.

## 9. UI Rules

**`_docs/ui.md` is the single source of truth** for design tokens, typography, component inventory, page layouts, states, responsive rules, and accessibility. This section summarises `_docs/design-system.md` and points to `_docs/ui.md` for the authoritative details.

### Stack (from `_docs/design-system.md` section 1)

| Concern | Choice |
|---|---|
| UI library | React 18 with function components and hooks |
| Build tool / dev server | Vite |
| Language | TypeScript (`strict: true`) |
| Styling | Tailwind CSS utility classes |
| Component primitives | shadcn/ui |
| Server state | TanStack Query |
| Client state | Zustand |
| Toasts | Sonner (`Toaster` mounted in `frontend/src/main.tsx`) |
| Icons | `lucide-react` |
| QR code | `qrcode.react` |

There is **no server-side template layer** and **no CSS framework CDN** in this project.

### Where the rules live (from `_docs/design-system.md` section 2)

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

### Wiring the tokens into Tailwind (from `_docs/design-system.md` section 3)

Colour and font values are defined only in `_docs/ui.md`. They are registered once, in `frontend/tailwind.config.js`, during F-02:

- Status colours (`WAITING`, `CALLED`, `SEATED`, `NO_SHOW`, `CANCELLED`, `DONE`) and table statuses (`AVAILABLE`, `OCCUPIED`, `CLEANING`) become theme colours, so components reference semantic names, never hex literals.
- The `Inter` family with `Noto Sans TC` fallback becomes the sans stack.
- Components then use utilities (`bg-called`, `text-primary`, `rounded-2xl`) rather than inline styles or hardcoded hex values.

**Rule: no hex colour literal appears in a `.tsx` file.** If a token is missing, it is added to `_docs/ui.md` first, then to `tailwind.config.js`.

### Component conventions (from `_docs/design-system.md` section 4)

- Primitives come from shadcn/ui (`Button`, `Input`, `Label`, `Card`, `Dialog`, `Select`, `Badge`, `Table`, `Skeleton`, `Switch`, `Checkbox`, `Form`); the project-specific components listed in `_docs/ui.md` section 5 live in `frontend/src/components/`.
- One component per file, file named after the component, imported through the `@` alias.
- A component that appears in a page mock-up but not in `_docs/ui.md` section 5 is not built: `_docs/ui.md` is extended by a docs issue first.
- Reusable props are documented in `_docs/ui.md` section 19.

### State rendering (from `_docs/design-system.md` section 5)

Every screen renders four states, defined in `_docs/ui.md` sections 7-9:

1. **Loading**: `LoadingSkeleton` with the variant named for the page.
2. **Empty**: `EmptyState` with icon, title, description, and action.
3. **Error**: the message mapped from the error code in `_docs/specs.md` section 11; unexpected failures surface through `ConnectionBanner` or a toast.
4. **Data**: the page body.

Server data is read through TanStack Query hooks keyed off `frontend/src/api/queryKeys.ts`; mutations invalidate those keys. Auth token and sound preference live in the Zustand `staffStore` and nowhere else.

### Responsive and accessibility (from `_docs/design-system.md` section 6)

- Guest pages are mobile-first and width-capped; staff pages are tablet/desktop-first. Breakpoints and per-page rules: `_docs/ui.md` section 10.
- Icon buttons carry `aria-label`, dialogs trap focus, status text is announced politely, contrast stays at or above 4.5:1: `_docs/ui.md` section 11.
- Sizing uses `rem`, and 200% browser zoom must not break the layout: `_docs/ui.md` section 3.

### Copy rules (from `_docs/design-system.md` section 7)

- All UI text is English. No CJK characters ship in user-visible strings.
- Date and time display as `2026-09-10 21:00`.
- Phone numbers display as Taiwan format (`09xx-xxx-xxx` / `02-xxxx-xxxx`).
- Copy for each page is specified in `_docs/ui.md` section 6; reproduce it rather than inventing new wording.

### Theme (from `_docs/design-system.md` section 8)

Light theme only in v1. Dark mode and i18n are non-goals; see `_docs/ui.md` sections 17 and 18.

## 10. State Machine

Summarised from `_docs/specs.md` section 5. The authoritative source with all 23 transition rules and 10 dash-item state lines is `_docs/specs.md` section 5.

### Waitlist states (6 states)

- `WAITING` → `CALLED` (Call)
- `WAITING` → `SEATED` (Seat)
- `WAITING` → `CANCELLED` (Cancel)
- `CALLED` → `SEATED` (Seat)
- `CALLED` → `NO_SHOW` (No-show or timeout)
- `CALLED` → `WAITING` (Revert)
- `CALLED` → `CANCELLED` (Cancel with confirm)
- `SEATED` → `DONE` (Release table)
- `SEATED` → `CANCELLED` (Staff cancel)
- `NO_SHOW` → `WAITING` (Restore)
- `CANCELLED` → terminal
- `DONE` → terminal

### Table states (3 states)

- `AVAILABLE` ↔ `CLEANING` (manual)
- `AVAILABLE` → `OCCUPIED` (seat)
- `OCCUPIED` → `AVAILABLE` (release)

### Rules

- `OCCUPIED` cannot be set directly via `PATCH /staff/tables/{id}`.
- `CALLED` timeout uses `hold_minutes_snapshot`.
- Lazy no-show evaluates on read.
- Release table sets entry to `DONE`.
- Cancel releases table if any.
- Close day closes all active entries.

## 11. Time and Timezone

Summarised from `_docs/specs.md` section 13.

- Store UTC.
- Display `Asia/Taipei`.
- Date format: `2026-09-10`.
- DateTime format: `2026-09-10 21:00`.
- `business_date` uses branch timezone and cutoff hour (default 4).
- `remaining_seconds` returned by backend for `CALLED` entries.
- Frontend does not compute time differences.

## 12. Queue Number

Summarised from `_docs/specs.md` section 8.

- `seq` = max seq for `(branch_id, business_date, queue_prefix)` + 1.
- `queue_number` display: `A001`.
- `full_queue_number` unique: `A-20260910-001`.
- Resets daily.
- Not unique across days.
- Guest lookup without token only searches current `business_date`.

## 13. Errors

Summarised from `_docs/specs.md` section 11. All errors use the shape:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": {}
  }
}
```

### Error codes (13 codes)

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

### Frontend-only code

- `NETWORK_ERROR` — synthesised client-side by the API client when a request never reaches the backend.

Frontend maps codes to English messages in `api/errors.ts`.

## 14. Testing

### Backend (does not exist yet, tracked by Platform Issue 12)

```bash
uv run pytest
```

### Frontend (does not exist yet, tracked by Platform Issue 12)

```bash
npm run test
```

### Makefile target (does not exist yet, tracked by Platform Issue 12)

```bash
make test
```

Commands reference: `_docs/testing.md` section 8, `_docs/plan.md` F-01.

No test commands run in this checkout until Platform Issue 12 creates `Makefile`, `backend/` and `frontend/`.

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

From `CONTRIBUTING.md` ## File Ownership (Platform #9, closed). `_docs/documents.md` wins on role reachability where there is a conflict.

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

### Recorded divergences

1. `_docs/documents.md:27` lists the agent guide as `_docs/AGENTS.md`, a path that does not exist; the real file is root `AGENTS.md`. **No owning issue exists** for `_docs/documents.md`.
2. `_docs/documents.md:12` and `:14` grant SA and SW write/read access to `_docs/design-system.md`, which will not exist after the follow-up deletion. **No owning issue exists**.
