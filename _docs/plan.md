# TableQueue — Implementation Plan

Version: 0.1.0
Last updated: 2026-09-10

This plan lists every issue for building TableQueue, grouped by phase.
Each issue follows the task template in `CONTRIBUTING.md`.

Legend:
- ID: unique issue ID (phase-prefixed)
- Size: S / M / L
- Deps: blocked by

---

## Index

### Phase 0 — Specs & Docs (done before coding)
- P0-01 Write `_docs/specs.md`
- P0-02 Write `_docs/ui.md`
- P0-03 Write `_docs/openapi.yaml`
- P0-04 Write `_docs/testing.md`
- P0-05 Write `_docs/deployment.md`
- P0-06 Write `_docs/api-examples.md`
- P0-07 Write `_docs/demo.md`
- P0-08 Write `README.md`
- P0-09 Write `CONTRIBUTING.md`
- P0-10 Write `AGENTS.md`
- P0-11 Write `_docs/plan.md` (this file)

### Phase 1 — Frontend + Mock
- F-01 Setup repo structure
- F-02 Init frontend project
- F-03 API client and mock layer
- F-04 Zustand store and query keys
- F-05 Layouts and routing
- F-06 Shared components
- F-07 JoinPage
- F-08 StatusPage
- F-09 LookupPage
- F-10 BoardPage
- F-11 LoginPage
- F-12 WaitlistPage
- F-13 TablesPage
- F-14 SettingsPage
- F-15 Frontend tests

### Phase 2 — Backend + Mock DB
- B-01 Init backend project
- B-02 SQLAlchemy models
- B-03 Pydantic schemas
- B-04 Errors and dependencies
- B-05 Auth endpoints
- B-06 Public endpoints
- B-07 Staff waitlist endpoints
- B-08 Staff tables endpoints
- B-09 Staff dashboard endpoint
- B-10 Admin settings endpoints
- B-11 Admin tables endpoints
- B-12 Admin reset endpoint
- B-13 Seed script
- B-14 Backend tests

### Phase 3 — Integration
- I-01 Switch frontend to real API
- I-02 Verify end-to-end flow

### Phase 4 — Database
- D-01 Swap mock store for real SQLAlchemy DB
- D-02 Add more tests
- D-03 Verify all tests pass

---

# Phase 0 — Specs & Docs

## P0-01 Write `_docs/specs.md`
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: L
- **Deps**: None
- **Goal**: Produce the full specification covering roles, flows, state machine, data model, business rules, error codes, API summary, time/timezone, concurrency, security, known limitations, non-goals.
- **Acceptance criteria**:
  - [ ] File exists at `_docs/specs.md`
  - [ ] Contains all 21 sections listed in the earlier draft
  - [ ] All decisions from Phase 0 Q&A are captured
- **Out of scope**: Any code.
- **Constraints**: English only.

## P0-02 Write `_docs/ui.md`
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: L
- **Deps**: P0-01
- **Goal**: Produce UI guide covering design principles, tokens, typography, components, pages, states, responsive, a11y, motion, sounds, icons.
- **Acceptance criteria**:
  - [ ] File exists at `_docs/ui.md`
  - [ ] All 19 sections present
  - [ ] Color tokens match `_docs/specs.md`
- **Out of scope**: Code.

## P0-03 Write `_docs/openapi.yaml`
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: L
- **Deps**: P0-01
- **Goal**: Produce OpenAPI 3.0.3 contract for all endpoints.
- **Acceptance criteria**:
  - [ ] File exists at `_docs/openapi.yaml`
  - [ ] All endpoints from `_docs/specs.md#12-api-summary` present
  - [ ] All schemas in `components.schemas` present
  - [ ] Examples included
- **Out of scope**: Implementation.

## P0-04 Write `_docs/testing.md`
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: M
- **Deps**: P0-01
- **Goal**: Produce testing strategy, test names, fixtures, time injection, coverage goals, non-goals, commands.
- **Acceptance criteria**:
  - [ ] File exists at `_docs/testing.md`
  - [ ] Test names listed for backend and frontend
  - [ ] Commands documented
- **Out of scope**: Writing tests.

## P0-05 Write `_docs/deployment.md`
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: M
- **Deps**: P0-01
- **Goal**: Produce local dev guide, env vars, DB notes, future deployment notes, known limitations, troubleshooting.
- **Acceptance criteria**:
  - [ ] File exists at `_docs/deployment.md`
  - [ ] All env vars documented
  - [ ] Local dev commands documented
- **Out of scope**: Actual deployment.

## P0-06 Write `_docs/api-examples.md`
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: S
- **Deps**: P0-03
- **Goal**: Produce curl examples for every endpoint.
- **Acceptance criteria**:
  - [ ] File exists at `_docs/api-examples.md`
  - [ ] Every endpoint from `_docs/openapi.yaml` has a curl example
  - [ ] Error examples included
- **Out of scope**: Code.

## P0-07 Write `_docs/demo.md`
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: S
- **Deps**: P0-01
- **Goal**: Produce step-by-step demo script.
- **Acceptance criteria**:
  - [ ] File exists at `_docs/demo.md`
  - [ ] Steps 1–10 included
  - [ ] Demo checklist included
- **Out of scope**: Code.

## P0-08 Write `README.md`
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: M
- **Deps**: P0-01, P0-03, P0-05
- **Goal**: Produce README with overview, tech stack, structure, getting started, env vars, demo, docs links, known limitations.
- **Acceptance criteria**:
  - [ ] File exists at repo root
  - [ ] All sections present
  - [ ] Commands match `Makefile`
- **Out of scope**: Code.

## P0-09 Write `CONTRIBUTING.md`
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: M
- **Deps**: P0-01
- **Goal**: Produce contribution guide with issue workflow, task template, labels, milestones, branch naming, commit convention, PR flow, testing, DoD, agent rules.
- **Acceptance criteria**:
  - [ ] File exists at repo root
  - [ ] Task template included
  - [ ] Labels and milestones listed
- **Out of scope**: Code.

## P0-10 Write `AGENTS.md`
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: M
- **Deps**: P0-01, P0-09
- **Goal**: Produce agent guide with hard rules, structure, commands, backend/frontend guidelines, state machine, errors, testing, do-not-do list.
- **Acceptance criteria**:
  - [ ] File exists at repo root
  - [ ] All 17 sections present
- **Out of scope**: Code.

## P0-11 Write `_docs/plan.md`
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: M
- **Deps**: P0-01
- **Goal**: Produce this plan.
- **Acceptance criteria**:
  - [ ] File exists at `_docs/plan.md`
  - [ ] All issues listed
- **Out of scope**: Code.

---

# Phase 1 — Frontend + Mock

## F-01 Setup repo structure
- **Phase**: phase-1-frontend-mock
- **Type**: chore
- **Area**: frontend
- **Size**: S
- **Deps**: P0-08, P0-09, P0-10
- **Goal**: Create monorepo structure with `backend/`, `frontend/`, `_docs/`, root `package.json`, `Makefile`, `.gitignore`, `.editorconfig`, `.nvmrc`.
- **Acceptance criteria**:
  - [ ] `backend/pyproject.toml` exists
  - [ ] `frontend/package.json` exists
  - [ ] Root `package.json` with `concurrently`
  - [ ] `Makefile` with targets: `setup`, `dev`, `backend`, `frontend`, `seed`, `test`, `test-backend`, `test-frontend`, `lint`, `format`
  - [ ] `.gitignore` includes `node_modules/`, `.venv/`, `__pycache__/`, `dev.db`, `.env`, `dist/`
  - [ ] `.editorconfig`: Python 4-space, TS 2-space, LF, UTF-8
  - [ ] `.nvmrc` contains `20`
- **Out of scope**: Actual backend or frontend code.
- **Constraints**: Follow `README.md` structure exactly.

## F-02 Init frontend project
- **Phase**: phase-1-frontend-mock
- **Type**: chore
- **Area**: frontend
- **Size**: S
- **Deps**: F-01
- **Goal**: Initialize React + Vite + TS + Tailwind + shadcn/ui.
- **Acceptance criteria**:
  - [ ] `frontend/package.json` with deps per `AGENTS.md`
  - [ ] `vite.config.ts` with React plugin, `@` alias, `/api` proxy, Vitest config
  - [ ] `tsconfig.json` strict
  - [ ] `tailwind.config.js` with status colors and fonts
  - [ ] `postcss.config.js`
  - [ ] `index.html` with `TableQueue` title and fonts
  - [ ] `src/main.tsx` with `QueryClientProvider`, `BrowserRouter`, `ErrorBoundary`, `Toaster`
  - [ ] `src/index.css` with Tailwind directives
  - [ ] `.env.example` with all frontend vars
  - [ ] `npm run dev` starts
  - [ ] `npm run build` succeeds
- **Out of scope**: Pages, API client, mock.
- **Constraints**: English UI only, no dark mode.

## F-03 API client and mock layer
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Deps**: F-02
- **Goal**: Centralized API client and mock layer.
- **Acceptance criteria**:
  - [ ] `src/api/client.ts` with base URL, auth header, 30s timeout, 401/429/5xx handling, `NETWORK_ERROR`
  - [ ] `src/api/errors.ts` with `ApiError` and `getErrorMessage`
  - [ ] `src/api/queryKeys.ts` with all keys
  - [ ] `src/api/mock/` with responses matching `_docs/openapi.yaml`
  - [ ] `VITE_USE_MOCK` toggles mock vs real
  - [ ] Mock data matches seed data
- **Out of scope**: Pages, components.
- **Constraints**: All backend calls through `api/client.ts`.

## F-04 Zustand store and query keys
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: S
- **Deps**: F-02
- **Goal**: Create `staffStore` and centralize query keys.
- **Acceptance criteria**:
  - [ ] `staffStore.ts` with `token`, `soundEnabled`, `setToken`, `logout`, `setSoundEnabled`, `persist`
  - [ ] `queryKeys.ts` with all keys
  - [ ] Persist under `staff-storage`
- **Out of scope**: Pages.

## F-05 Layouts and routing
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Deps**: F-02
- **Goal**: Create layouts, routes, `NotFoundPage`, `DevBadge`.
- **Acceptance criteria**:
  - [ ] `routes.ts` with constants
  - [ ] `App.tsx` with all routes
  - [ ] `PublicLayout.tsx`, `StaffLayout.tsx`
  - [ ] `NotFoundPage.tsx`, `DevBadge.tsx`
  - [ ] `StaffLayout` redirects to `/staff/login` if no token
- **Out of scope**: Page content.

## F-06 Shared components
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Deps**: F-02
- **Goal**: Create shared components listed in `_docs/ui.md`.
- **Acceptance criteria**:
  - [ ] `StatusBadge`, `Countdown`, `WaitlistCard`, `TableCard`, `EmptyState`, `LoadingSkeleton`, `ConfirmDialog`, `ConnectionBanner`, `SoundToggle`, `QrCode`
  - [ ] `useCountdown`
  - [ ] All match `_docs/ui.md`
  - [ ] All icon buttons have `aria-label`
- **Out of scope**: Pages.

## F-07 JoinPage
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Deps**: F-05, F-06
- **Goal**: Build `/join` page.
- **Acceptance criteria**:
  - [ ] Reads `branch` query, falls back to `VITE_BRANCH_ID`
  - [ ] Calls `usePublicBranch`
  - [ ] Shows closed message when `is_waitlist_open=false`
  - [ ] Form: name, phone, party size, note
  - [ ] Validates per `_docs/specs.md#7-business-rules`
  - [ ] On success: navigate to `/status/{queueNumber}?token={statusToken}`
  - [ ] On duplicate phone: show error and `View Status` button
- **Out of scope**: Backend.

## F-08 StatusPage
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Deps**: F-05, F-06
- **Goal**: Build `/status/:queueNumber` page.
- **Acceptance criteria**:
  - [ ] Reads `token` from query; if missing, shows last-3-digits form
  - [ ] Calls `useStatus`
  - [ ] Progress bar `Waiting → Called → Seated`
  - [ ] Shows `N groups ahead`, `Estimated wait`
  - [ ] `CALLED`: orange, countdown, vibration, sound toggle
  - [ ] `WAITING`: `Cancel`
  - [ ] `CALLED`: `Cancel` with confirm
  - [ ] `CANCELLED`: `Join Again`
  - [ ] `SEATED`: `You're seated. Enjoy your meal!`
  - [ ] Polls every 5s, refetch on focus, refetch at countdown 0
- **Out of scope**: Backend.

## F-09 LookupPage
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: S
- **Deps**: F-05, F-06
- **Goal**: Build `/lookup` page.
- **Acceptance criteria**:
  - [ ] Fields: queue number, last 3 digits
  - [ ] On success: navigate to `/status/{queueNumber}?token={statusToken}`
  - [ ] On failure: `No matching waitlist entry found.`
- **Out of scope**: Backend.

## F-10 BoardPage
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Deps**: F-05, F-06
- **Goal**: Build `/board/:branchId` public board.
- **Acceptance criteria**:
  - [ ] Reads `branchId` from path
  - [ ] Calls `useBoard`
  - [ ] Shows restaurant name, branch, hours, waitlist status
  - [ ] `Now Serving`, `Next up`, `Recent calls` (max 3), `Waiting`
  - [ ] QR code with join URL
  - [ ] Polls every 5s
  - [ ] Never shows names or phones
- **Out of scope**: Backend.

## F-11 LoginPage
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: S
- **Deps**: F-05, F-06
- **Goal**: Build `/staff/login` page.
- **Acceptance criteria**:
  - [ ] Single PIN input, `Remember me`, `Login`
  - [ ] Error: `Invalid PIN.`
  - [ ] On success: store token, navigate to `/staff/waitlist`
  - [ ] Redirect if already logged in
- **Out of scope**: Backend.

## F-12 WaitlistPage
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: L
- **Deps**: F-05, F-06
- **Goal**: Build `/staff/waitlist` page.
- **Acceptance criteria**:
  - [ ] Stats cards
  - [ ] Search, filter, pause switch, close day
  - [ ] List with cards and actions: `Call`, `Seat`, `No-show`, `Restore`, `Revert`, `Cancel`, `Edit`
  - [ ] `CALLED` cards show countdown
  - [ ] Up/down reorder in v1
  - [ ] Collapsible closed section
  - [ ] `Last updated: HH:MM:SS`
  - [ ] Polls every 3s
- **Out of scope**: Backend.

## F-13 TablesPage
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Deps**: F-05, F-06
- **Goal**: Build `/staff/tables` page.
- **Acceptance criteria**:
  - [ ] Grid `2/3/4` columns
  - [ ] Cards show label, capacity, status
  - [ ] `AVAILABLE` ↔ `CLEANING`
  - [ ] `OCCUPIED` shows `A012 · 4 pax · 25 min` and `Release Table`
  - [ ] Empty state
  - [ ] Polls every 5s
- **Out of scope**: Backend.

## F-14 SettingsPage
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: L
- **Deps**: F-05, F-06
- **Goal**: Build `/admin/settings` page.
- **Acceptance criteria**:
  - [ ] Sections: Store Info, Waitlist Settings, Tables, Notifications & Sound, Danger Zone
  - [ ] Each section has own `Save`
  - [ ] Table CRUD
  - [ ] Change PIN
  - [ ] Reset Data (dev only)
- **Out of scope**: Backend.

## F-15 Frontend tests
- **Phase**: phase-1-frontend-mock
- **Type**: test
- **Area**: frontend
- **Size**: M
- **Deps**: F-03, F-06, F-07, F-08
- **Goal**: Add Vitest + RTL tests.
- **Acceptance criteria**:
  - [ ] `api/client.test.ts`, `api/errors.test.ts`
  - [ ] `components/StatusBadge.test.tsx`, `Countdown.test.tsx`, `WaitlistCard.test.tsx`, `TableCard.test.tsx`
  - [ ] `pages/JoinPage.test.tsx`, `StatusPage.test.tsx`
  - [ ] `npm run test` passes
- **Out of scope**: E2E.

---

# Phase 2 — Backend + Mock DB

## B-01 Init backend project
- **Phase**: phase-2-backend
- **Type**: chore
- **Area**: backend
- **Size**: S
- **Deps**: F-01
- **Goal**: Initialize FastAPI backend with uv, SQLAlchemy 2.0, Pydantic v2, config, health endpoint.
- **Acceptance criteria**:
  - [ ] `backend/pyproject.toml` with dependencies from `_docs/deployment.md`
  - [ ] `backend/.env.example` with all backend vars
  - [ ] `backend/app/main.py` with FastAPI app and `lifespan`
  - [ ] `backend/app/config.py` with `pydantic-settings`
  - [ ] `backend/app/database.py` with SQLAlchemy engine and `SessionLocal`
  - [ ] `GET /health` returns `{ status, version, env }`
  - [ ] `uv run uvicorn app.main:app --reload` starts without errors
  - [ ] Swagger UI shows `/health`
  - [ ] Startup creates default Restaurant, Branch, Settings if missing
- **Test requirements**:
  - [ ] `backend/tests/test_health.py::test_health_ok`
  - [ ] `backend/tests/test_health.py::test_health_env`
- **Implementation notes**:
  - Python 3.11+
  - No Alembic in v1
  - `create_all` on startup
  - `ENV` variable drives `development` / `test` / `production`
- **Dependencies**: Blocked by F-01. Blocks B-02, B-03, B-04.
- **Out of scope**: Business logic, endpoints beyond `/health`.
- **Constraints**: Files in `backend/`. Do not add features not in `_docs/specs.md`.

## B-02 SQLAlchemy models
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Deps**: B-01
- **Goal**: Create SQLAlchemy 2.0 models for Restaurant, Branch, Table, WaitlistEntry, Settings.
- **Acceptance criteria**:
  - [ ] `backend/app/models.py` with all 5 models
  - [ ] All fields match `_docs/specs.md#6-data-model`
  - [ ] Enums: `WaitlistStatus`, `TableStatus`, `WaitlistSource`, `CancelledReason`
  - [ ] Unique constraints:
    - `(branch_id, business_date, queue_prefix, seq)` on WaitlistEntry
    - `(branch_id, label)` on Table
    - `branch_id` on Settings
  - [ ] Indexes:
    - `(branch_id, business_date, status)` on WaitlistEntry
    - `(branch_id, sort_order)` on WaitlistEntry
    - `(branch_id, is_active, status)` on Table
  - [ ] Foreign keys per spec
  - [ ] `created_at` and `updated_at` use Python `datetime.now(timezone.utc)`
- **Test requirements**:
  - [ ] `test_models.py::test_create_all`
  - [ ] `test_models.py::test_unique_queue_number`
  - [ ] `test_models.py::test_unique_table_label`
  - [ ] `test_models.py::test_settings_unique_branch`
- **Implementation notes**:
  - SQLAlchemy 2.0 style with `Mapped[]` and `mapped_column()`
  - UUID PK for Table and WaitlistEntry
  - Integer PK for Restaurant, Branch, Settings
- **Dependencies**: Blocked by B-01. Blocks B-03, B-13, B-14.
- **Out of scope**: Schemas, endpoints, business logic.
- **Constraints**: Files in `backend/app/models.py`.

## B-03 Pydantic schemas
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Deps**: B-01
- **Goal**: Create Pydantic v2 request/response schemas matching `_docs/openapi.yaml`.
- **Acceptance criteria**:
  - [ ] `backend/app/schemas.py` with all schemas
  - [ ] Request schemas: `JoinWaitlistRequest`, `CancelWaitlistRequest`, `StaffLoginRequest`, `ChangePinRequest`, `SeatWaitlistRequest`, `EditWaitlistRequest`, `ReorderWaitlistRequest`, `UpdateTableStatusRequest`, `CreateTableRequest`, `UpdateTableRequest`, `UpdateSettingsRequest`, `ResetDataRequest`
  - [ ] Response schemas: `WaitlistEntryResponse`, `WaitlistListResponse`, `WaitlistStatusResponse`, `TableResponse`, `TableListResponse`, `DashboardResponse`, `SettingsResponse`, `PublicBranchResponse`, `BoardResponse`, `HealthResponse`, `ErrorResponse`, `StaffLoginResponse`
  - [ ] Request and response are separate classes
  - [ ] `model_config = ConfigDict(from_attributes=True)` on response schemas
  - [ ] Validation matches `_docs/specs.md#7-business-rules`
- **Test requirements**:
  - [ ] `test_schemas.py::test_join_waitlist_validation`
  - [ ] `test_schemas.py::test_party_size_range`
  - [ ] `test_schemas.py::test_change_pin_mismatch`
  - [ ] `test_schemas.py::test_note_max_length`
- **Implementation notes**:
  - Pydantic v2
  - Use `Field` for constraints
  - Use `field_validator` where needed
  - snake_case only
- **Dependencies**: Blocked by B-01. Blocks B-05, B-06, B-07, B-08, B-09, B-10, B-11, B-12.
- **Out of scope**: Endpoints, business logic.
- **Constraints**: Files in `backend/app/schemas.py`.

## B-04 Errors and dependencies
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Deps**: B-01
- **Goal**: Create `AppError`, global exception handlers, and FastAPI dependencies.
- **Acceptance criteria**:
  - [ ] `backend/app/errors.py` with `AppError`
  - [ ] Exception handlers for `AppError`, `RequestValidationError`, `Exception`
  - [ ] `backend/app/dependencies.py` with `get_db`, `get_current_staff`, `get_now`
  - [ ] `HTTPBearer` security scheme
  - [ ] All error codes from `_docs/specs.md#11-error-codes` defined
  - [ ] Unhandled exceptions return `INTERNAL_ERROR` without stack trace
- **Test requirements**:
  - [ ] `test_errors.py::test_app_error_handler`
  - [ ] `test_errors.py::test_validation_error_handler`
  - [ ] `test_errors.py::test_get_current_staff_invalid`
  - [ ] `test_errors.py::test_internal_error_no_stack`
- **Implementation notes**:
  - Routers do not catch; raise `AppError`
  - Never log phone, name, token
- **Dependencies**: Blocked by B-01. Blocks B-05 through B-12.
- **Out of scope**: Endpoints, business logic.
- **Constraints**: Files in `backend/app/errors.py`, `backend/app/dependencies.py`.

## B-05 Auth endpoints
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Deps**: B-02, B-03, B-04
- **Goal**: Implement `POST /api/v1/auth/login` and `POST /api/v1/auth/change-pin`.
- **Acceptance criteria**:
  - [ ] Login validates PIN against `Settings.staff_pin_hash`, fallback to `STAFF_PIN`
  - [ ] Returns JWT with `sub=staff`, `role=staff`, `iat`, `exp`
  - [ ] Rate limit: 5/minute per IP
  - [ ] Change PIN validates current, new, confirm; new ≠ current
  - [ ] Change PIN updates `staff_pin_hash`
  - [ ] Errors: `AUTH_INVALID_PIN`, `AUTH_RATE_LIMITED`, `VALIDATION_ERROR`
- **Test requirements**:
  - [ ] `test_auth.py::test_login_success`
  - [ ] `test_auth.py::test_login_invalid_pin`
  - [ ] `test_auth.py::test_login_rate_limited`
  - [ ] `test_auth.py::test_change_pin_success`
  - [ ] `test_auth.py::test_change_pin_invalid_current`
  - [ ] `test_auth.py::test_change_pin_mismatch`
  - [ ] `test_auth.py::test_change_pin_same_as_current`
- **Implementation notes**:
  - `passlib[bcrypt]` for hashing
  - `python-jose` for JWT
  - `slowapi` for rate limit
- **Dependencies**: Blocked by B-02, B-03, B-04. Blocks I-01.
- **Out of scope**: Refresh tokens, logout endpoint.
- **Constraints**: Files in `backend/app/routers/auth.py`.

## B-06 Public endpoints
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: L
- **Deps**: B-02, B-03, B-04
- **Goal**: Implement public endpoints.
- **Acceptance criteria**:
  - [ ] `GET /api/v1/public/branches/{branch_id}` returns store info and `is_waitlist_open`
  - [ ] `GET /api/v1/public/branches/{branch_id}/board` returns current call, next up, recent calls, waiting count
  - [ ] `POST /api/v1/branches/{branch_id}/waitlist` creates entry, checks duplicate phone, generates queue number
  - [ ] `GET /api/v1/waitlist/{queue_number}` returns status with token or `phone_last3`
  - [ ] `POST /api/v1/waitlist/{queue_number}/cancel` cancels with token or `phone_last3`
  - [ ] Rate limit on join and lookup: 10/minute per IP
  - [ ] Rate limit on public branch and board: 30/minute per IP
- **Test requirements**:
  - [ ] `test_public_waitlist.py::test_join_waitlist_success`
  - [ ] `test_public_waitlist.py::test_join_waitlist_duplicate_phone`
  - [ ] `test_public_waitlist.py::test_join_waitlist_closed`
  - [ ] `test_public_waitlist.py::test_join_waitlist_invalid_phone`
  - [ ] `test_public_waitlist.py::test_get_status_with_token`
  - [ ] `test_public_waitlist.py::test_get_status_with_phone_last3`
  - [ ] `test_public_waitlist.py::test_get_status_wrong_last3`
  - [ ] `test_public_waitlist.py::test_cancel_waitlist_by_guest`
  - [ ] `test_public_waitlist.py::test_cancel_called_requires_confirmation`
  - [ ] `test_public_board.py::test_get_public_branch_success`
  - [ ] `test_public_board.py::test_get_board_success`
  - [ ] `test_public_board.py::test_get_board_empty`
- **Implementation notes**:
  - Queue number uses `business_date` + `seq`
  - `status_token` = `secrets.token_urlsafe(32)`
  - Board never returns names or phones
- **Dependencies**: Blocked by B-02, B-03, B-04. Blocks I-01.
- **Out of scope**: External notifications.
- **Constraints**: Files in `backend/app/routers/public.py`.

## B-07 Staff waitlist endpoints
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: L
- **Deps**: B-02, B-03, B-04, B-06
- **Goal**: Implement staff waitlist endpoints.
- **Acceptance criteria**:
  - [ ] `GET /api/v1/staff/waitlist` with `status`, `search`, `party_size`, `limit`, `offset`
  - [ ] `POST /api/v1/staff/waitlist/{id}/call` sets `CALLED`, stores `called_at`, `hold_minutes_snapshot`
  - [ ] `POST /api/v1/staff/waitlist/{id}/seat` sets `SEATED`, sets `table_id`, sets table `OCCUPIED` in one transaction
  - [ ] `POST /api/v1/staff/waitlist/{id}/no-show` sets `NO_SHOW`, releases table if any
  - [ ] `POST /api/v1/staff/waitlist/{id}/restore` sets `WAITING`, clears `called_at`, `closed_at`, `hold_minutes_snapshot`
  - [ ] `POST /api/v1/staff/waitlist/{id}/revert` sets `WAITING`, clears `called_at`, `hold_minutes_snapshot`
  - [ ] `POST /api/v1/staff/waitlist/{id}/cancel` sets `CANCELLED`, releases table
  - [ ] `POST /api/v1/staff/waitlist/{id}/edit` updates `party_size`, `note`
  - [ ] `POST /api/v1/staff/waitlist/reorder` updates `sort_order` in one transaction
  - [ ] Lazy no-show applied on list read
  - [ ] Phone masked in response
- **Test requirements**:
  - [ ] `test_staff_waitlist.py::test_list_waitlist_active`
  - [ ] `test_staff_waitlist.py::test_list_waitlist_closed`
  - [ ] `test_staff_waitlist.py::test_list_waitlist_search_name`
  - [ ] `test_staff_waitlist.py::test_call_waitlist_success`
  - [ ] `test_staff_waitlist.py::test_call_waitlist_invalid_status`
  - [ ] `test_staff_waitlist.py::test_seat_waitlist_success`
  - [ ] `test_staff_waitlist.py::test_seat_waitlist_table_not_available`
  - [ ] `test_staff_waitlist.py::test_no_show_waitlist_success`
  - [ ] `test_staff_waitlist.py::test_restore_waitlist_success`
  - [ ] `test_staff_waitlist.py::test_revert_waitlist_success`
  - [ ] `test_staff_waitlist.py::test_cancel_waitlist_by_staff`
  - [ ] `test_staff_waitlist.py::test_edit_waitlist_party_size`
  - [ ] `test_staff_waitlist.py::test_reorder_waitlist_success`
  - [ ] `test_staff_waitlist.py::test_reorder_waitlist_missing_ids`
- **Implementation notes**:
  - All state changes in transactions
  - `GET` triggers lazy no-show
  - `remaining_seconds` only for `CALLED`
- **Dependencies**: Blocked by B-02, B-03, B-04, B-06. Blocks I-01.
- **Out of scope**: Change table, drag-and-drop.
- **Constraints**: Files in `backend/app/routers/staff.py`.

## B-08 Staff tables endpoints
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Deps**: B-02, B-03, B-04
- **Goal**: Implement staff table endpoints.
- **Acceptance criteria**:
  - [ ] `GET /api/v1/staff/tables` returns active tables with `current_waitlist` for `OCCUPIED`
  - [ ] `PATCH /api/v1/staff/tables/{id}` accepts `AVAILABLE` or `CLEANING` only
  - [ ] `PATCH` rejects `OCCUPIED` with `VALIDATION_ERROR`
  - [ ] `POST /api/v1/staff/tables/{id}/release` releases `OCCUPIED` → `AVAILABLE`, sets entry `DONE` in one transaction
  - [ ] Release rejects non-`OCCUPIED` with `TABLE_NOT_AVAILABLE`
- **Test requirements**:
  - [ ] `test_staff_tables.py::test_list_tables_active`
  - [ ] `test_staff_tables.py::test_list_tables_includes_current_waitlist`
  - [ ] `test_staff_tables.py::test_update_table_status_available_to_cleaning`
  - [ ] `test_staff_tables.py::test_update_table_status_cleaning_to_available`
  - [ ] `test_staff_tables.py::test_update_table_status_occupied_rejected`
  - [ ] `test_staff_tables.py::test_release_table_success`
  - [ ] `test_staff_tables.py::test_release_table_not_occupied`
- **Implementation notes**:
  - `current_waitlist` only for `OCCUPIED`
  - `elapsed_minutes` = minutes since `seated_at`
- **Dependencies**: Blocked by B-02, B-03, B-04. Blocks I-01.
- **Out of scope**: Table merging, drag-and-drop.
- **Constraints**: Files in `backend/app/routers/staff.py`.

## B-09 Staff dashboard endpoint
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: S
- **Deps**: B-02, B-03, B-04, B-07, B-08
- **Goal**: Implement `GET /api/v1/staff/dashboard`.
- **Acceptance criteria**:
  - [ ] Returns `waiting_count`, `called_count`, `seated_count`
  - [ ] Returns `available_table_count`, `occupied_table_count`, `cleaning_table_count`
  - [ ] Returns `no_show_today`, `cancelled_today`, `seated_today` (business_date)
  - [ ] Returns `avg_wait_minutes_today` (null if no data)
  - [ ] Applies lazy no-show first
- **Test requirements**:
  - [ ] `test_staff_dashboard.py::test_dashboard_counts`
  - [ ] `test_staff_dashboard.py::test_dashboard_avg_wait_null_when_no_data`
- **Implementation notes**:
  - `no_show_today`, `cancelled_today`, `seated_today` use current `business_date`
- **Dependencies**: Blocked by B-02, B-03, B-04, B-07, B-08. Blocks I-01.
- **Out of scope**: Historical reports, CSV.
- **Constraints**: Files in `backend/app/routers/staff.py`.

## B-10 Admin settings endpoints
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Deps**: B-02, B-03, B-04
- **Goal**: Implement `GET /api/v1/admin/settings` and `PATCH /api/v1/admin/settings`.
- **Acceptance criteria**:
  - [ ] `GET` returns store info, waitlist settings, notification templates, `has_pin`
  - [ ] `GET` never returns `staff_pin_hash`
  - [ ] `PATCH` updates allowed fields
  - [ ] `PATCH` validates ranges per `_docs/specs.md#7-business-rules`
  - [ ] `PATCH` validates `queue_prefix` 1–3 uppercase letters
  - [ ] `PATCH` validates `open_time`, `close_time` `HH:MM`
- **Test requirements**:
  - [ ] `test_admin_settings.py::test_get_settings_success`
  - [ ] `test_admin_settings.py::test_update_settings_success`
  - [ ] `test_admin_settings.py::test_update_settings_hold_minutes_out_of_range`
  - [ ] `test_admin_settings.py::test_update_settings_queue_prefix_invalid`
  - [ ] `test_admin_settings.py::test_update_settings_notification_templates`
- **Implementation notes**:
  - `has_pin` = `staff_pin_hash is not None`
  - Notification templates stored as JSON
- **Dependencies**: Blocked by B-02, B-03, B-04. Blocks I-01.
- **Out of scope**: PIN change (in auth).
- **Constraints**: Files in `backend/app/routers/admin.py`.

## B-11 Admin tables endpoints
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Deps**: B-02, B-03, B-04
- **Goal**: Implement admin table CRUD.
- **Acceptance criteria**:
  - [ ] `GET /api/v1/admin/tables` with `include_inactive`
  - [ ] `POST /api/v1/admin/tables` creates table, unique label per branch
  - [ ] `PATCH /api/v1/admin/tables/{id}` updates table, unique label per branch
  - [ ] `DELETE /api/v1/admin/tables/{id}` soft-deletes, rejects if `OCCUPIED` with `CONFLICT`
  - [ ] `label` 1–10 chars, `capacity` 1–20, `section` 0–50 chars
- **Test requirements**:
  - [ ] `test_admin_tables.py::test_create_table_success`
  - [ ] `test_admin_tables.py::test_create_table_duplicate_label`
  - [ ] `test_admin_tables.py::test_update_table_success`
  - [ ] `test_admin_tables.py::test_update_table_duplicate_label`
  - [ ] `test_admin_tables.py::test_delete_table_soft`
  - [ ] `test_admin_tables.py::test_delete_table_occupied_conflict`
  - [ ] `test_admin_tables.py::test_list_admin_tables_include_inactive`
- **Implementation notes**:
  - Soft delete via `is_active=false`
  - Inactive tables excluded from staff tables and suggestions
- **Dependencies**: Blocked by B-02, B-03, B-04. Blocks I-01.
- **Out of scope**: Hard delete.
- **Constraints**: Files in `backend/app/routers/admin.py`.

## B-12 Admin reset endpoint
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: S
- **Deps**: B-02, B-03, B-04, B-13
- **Goal**: Implement `POST /api/v1/admin/reset`.
- **Acceptance criteria**:
  - [ ] Only allowed when `ENV=development`
  - [ ] Requires body `{ "confirm": "RESET" }`
  - [ ] Returns `204` on success
  - [ ] Returns `403` in non-development
  - [ ] Runs seed reset
- **Test requirements**:
  - [ ] `test_admin_reset.py::test_reset_success_dev`
  - [ ] `test_admin_reset.py::test_reset_forbidden_production`
  - [ ] `test_admin_reset.py::test_reset_wrong_confirm`
- **Implementation notes**:
  - Reuse `app.seed --reset` logic
- **Dependencies**: Blocked by B-02, B-03, B-04, B-13. Blocks I-01.
- **Out of scope**: Production data reset.
- **Constraints**: Files in `backend/app/routers/admin.py`.

## B-13 Seed script
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Deps**: B-02
- **Goal**: Create `python -m app.seed` with `--reset`.
- **Acceptance criteria**:
  - [ ] Creates Restaurant `Sunny Bistro`, Branch `Taipei Xinyi`, Settings
  - [ ] Creates 10 tables: `A1–A4` (2 pax), `B1–B4` (4 pax), `C1–C2` (6 pax)
  - [ ] Creates 5 `WAITING`, 1 `CALLED` (3 min ago), 1 `SEATED` on `B1`, 1 `NO_SHOW`, 1 `CANCELLED`
  - [ ] All `business_date = today`
  - [ ] Phones `0900-000-001` to `0900-000-009`
  - [ ] Without `--reset`: skips existing data
  - [ ] With `--reset`: clears and re-seeds
- **Test requirements**:
  - [ ] `test_seed.py::test_seed_reset_creates_expected_data`
  - [ ] `test_seed.py::test_seed_without_reset_skips_existing`
- **Implementation notes**:
  - Idempotent without `--reset`
  - `--reset` truncates tables first
- **Dependencies**: Blocked by B-02. Blocks B-12, I-02.
- **Out of scope**: Frontend seed.
- **Constraints**: Files in `backend/app/seed.py`.

## B-14 Backend tests
- **Phase**: phase-2-backend
- **Type**: test
- **Area**: backend
- **Size**: L
- **Deps**: B-05 through B-13
- **Goal**: Ensure all backend tests pass.
- **Acceptance criteria**:
  - [ ] All test files listed in `_docs/testing.md` exist
  - [ ] `uv run pytest` passes
  - [ ] Coverage ≥ 80% on services and routers
  - [ ] `conftest.py` with `db`, `client`, `fixed_now`, `staff_token`, `auth_headers`
  - [ ] `factories.py` with `make_branch`, `make_table`, `make_waitlist_entry`, `make_settings`, `make_staff_token`
- **Test requirements**:
  - [ ] All tests pass
- **Implementation notes**:
  - in-memory SQLite
  - `freezegun` for time
  - Boundary tests for `business_date`
- **Dependencies**: Blocked by B-05 through B-13. Blocks I-01.
- **Out of scope**: E2E, concurrency.
- **Constraints**: Files in `backend/tests/`.

# Phase 3 — Integration

## I-01 Switch frontend to real API
- **Phase**: phase-3-integration
- **Type**: chore
- **Area**: frontend
- **Size**: M
- **Deps**: B-14, F-15
- **Goal**: Turn off mock, point frontend to backend, verify all endpoints.
- **Acceptance criteria**:
  - [ ] `frontend/.env` sets `VITE_USE_MOCK=false`
  - [ ] Vite proxy `/api` → `http://localhost:8000` works
  - [ ] `VITE_API_BASE_URL=/api/v1`
  - [ ] `VITE_BRANCH_ID=1`
  - [ ] `VITE_PUBLIC_BASE_URL` empty (uses `window.location.origin`)
  - [ ] `frontend/src/api/mock/` is bypassed when `VITE_USE_MOCK=false`
  - [ ] All frontend pages load real data
  - [ ] No CORS errors in console
  - [ ] Error codes display correct English messages
  - [ ] 401 redirects to `/staff/login`
  - [ ] `npm run test` still passes
- **Test requirements**:
  - [ ] Manual: open `/join?branch=1`, join, see status
  - [ ] Manual: open `/staff/login`, log in with PIN `1234`
  - [ ] Manual: call, seat, release, close day
  - [ ] Manual: open `/board/1`, see current call
  - [ ] Manual: open `/admin/settings`, change `hold_minutes`
- **Implementation notes**:
  - Answer the question: **Which URL does the frontend use to talk to the backend?**
    - Development: `/api/v1` via Vite proxy → `http://localhost:8000`
    - Production: `VITE_API_BASE_URL` set to backend URL
  - Do not change API shapes; `_docs/openapi.yaml` is the contract
  - Do not change backend logic in this issue
- **Dependencies**: Blocked by B-14, F-15. Blocks I-02.
- **Out of scope**: Backend changes.
- **Constraints**: Only frontend config and mock bypass. Do not edit `_docs/specs.md`.

## I-02 Verify end-to-end flow
- **Phase**: phase-3-integration
- **Type**: test
- **Area**: frontend
- **Size**: M
- **Deps**: I-01
- **Goal**: Verify full flow works end-to-end using `_docs/demo.md`.
- **Acceptance criteria**:
  - [ ] Run `make seed`
  - [ ] Run `make dev`
  - [ ] Step 1: Join waitlist → `/status/A006?token=...`
  - [ ] Step 2: Staff login → `/staff/waitlist`
  - [ ] Step 3: Call `A006` → guest page turns orange, countdown starts
  - [ ] Step 4: Seat `A006` on `A1` → table map shows `OCCUPIED`
  - [ ] Step 5: No-show and restore `A001`
  - [ ] Step 6: Open `/board/1` → shows current call, QR code
  - [ ] Step 7: Change `hold_minutes` in settings → new call uses new value
  - [ ] Step 8: Release table → entry `DONE`, table `AVAILABLE`
  - [ ] Step 9: Close day → all active closed
  - [ ] Step 10: Reset data (dev only)
  - [ ] `_docs/demo.md` checklist all checked
- **Test requirements**:
  - [ ] Manual: follow `_docs/demo.md` step by step
  - [ ] Optional: ask coding agent to use a browser to verify
- **Implementation notes**:
  - If any step fails, open a new bug issue; do not fix in this issue
  - Capture screenshots for the PR
- **Dependencies**: Blocked by I-01. Blocks D-01.
- **Out of scope**: Automated E2E tests.
- **Constraints**: Do not add features.

---

# Phase 4 — Database

## D-01 Swap mock store for real SQLAlchemy DB
- **Phase**: phase-4-database
- **Type**: chore
- **Area**: database
- **Size**: M
- **Deps**: I-02
- **Goal**: Confirm backend uses SQLAlchemy + SQLite as real DB (not in-memory mock), and app is database-agnostic.
- **Acceptance criteria**:
  - [ ] Backend uses SQLAlchemy 2.0 for all persistence
  - [ ] `DATABASE_URL` drives the connection string
  - [ ] Default dev: `sqlite:///./dev.db`
  - [ ] Test: `sqlite:///:memory:`
  - [ ] No raw SQL in routers
  - [ ] All writes go through service layer
  - [ ] Restart backend: data persists
  - [ ] Changing `DATABASE_URL` to PostgreSQL requires no code change
  - [ ] `Base.metadata.create_all` runs on startup
  - [ ] No Alembic in v1
- **Test requirements**:
  - [ ] Manual: restart backend, data still there
  - [ ] Manual: delete `dev.db`, restart, default Restaurant/Branch/Settings recreated
- **Implementation notes**:
  - Keep app database-agnostic
  - Use SQLAlchemy for all DB access
  - Do not import SQLite-specific code outside `database.py`
  - Write the answer to: **Which command do you use for running tests?**
    - `cd backend && uv run pytest`
- **Dependencies**: Blocked by I-02. Blocks D-02.
- **Out of scope**: Alembic migrations, production PostgreSQL.
- **Constraints**: Do not change API shapes. Do not edit `_docs/specs.md`.

## D-02 Add more tests
- **Phase**: phase-4-database
- **Type**: test
- **Area**: backend
- **Size**: M
- **Deps**: D-01
- **Goal**: Add more tests to cover database-specific behavior.
- **Acceptance criteria**:
  - [ ] Tests cover unique constraints at DB level
  - [ ] Tests cover transaction rollback on error
  - [ ] Tests cover `business_date` boundary with fixed time
  - [ ] Tests cover lazy no-show with fixed time
  - [ ] Tests cover close day transaction
  - [ ] Tests cover release table transaction
  - [ ] Tests cover seat transaction (entry + table)
  - [ ] Tests cover reorder transaction
  - [ ] `uv run pytest` passes
  - [ ] Coverage ≥ 80% on services and routers
- **Test requirements**:
  - [ ] Add tests to `test_state_machine.py`
  - [ ] Add tests to `test_models.py`
  - [ ] Add tests to `test_staff_waitlist.py`
  - [ ] Add tests to `test_staff_tables.py`
- **Implementation notes**:
  - Use in-memory SQLite for tests
  - Use `freezegun` for time
  - Ask agent for recommendations if unsure
- **Dependencies**: Blocked by D-01. Blocks D-03.
- **Out of scope**: Load tests, concurrency tests.
- **Constraints**: Files in `backend/tests/`.

## D-03 Verify all tests pass
- **Phase**: phase-4-database
- **Type**: test
- **Area**: backend
- **Size**: S
- **Deps**: D-02
- **Goal**: Final verification that everything passes and app still works.
- **Acceptance criteria**:
  - [ ] `cd backend && uv run pytest` passes
  - [ ] `cd frontend && npm run test` passes
  - [ ] `make test` passes
  - [ ] `make seed` runs
  - [ ] `make dev` runs
  - [ ] Manual demo from `_docs/demo.md` still works
  - [ ] No lint errors
  - [ ] All Phase 4 issues closed
- **Test requirements**:
  - [ ] Run all commands above
- **Implementation notes**:
  - If anything fails, open a new bug issue; do not fix in this issue
- **Dependencies**: Blocked by D-02. Blocks none.
- **Out of scope**: Production deployment.
- **Constraints**: Do not add features.

# Phase 0–4 — Dependency Graph, Ordering, and GitHub Metadata

This section defines:
- How issues depend on each other
- The recommended work order
- Labels and milestone mapping per issue
- GitHub metadata table for bulk creation

---

## 1. Dependency Graph

```text
Phase 0 (docs)
  P0-01 specs.md
    ├── P0-02 ui.md
    ├── P0-03 openapi.yaml
    │     └── P0-06 api-examples.md
    ├── P0-04 testing.md
    ├── P0-05 deployment.md
    │     └── P0-08 README.md
    ├── P0-07 demo.md
    ├── P0-09 CONTRIBUTING.md
    │     └── P0-10 AGENTS.md
    └── P0-11 plan.md

Phase 1 (frontend + mock)
  P0-08, P0-09, P0-10
    └── F-01 repo structure
          └── F-02 init frontend
                ├── F-03 api client + mock
                │     └── F-15 tests
                ├── F-04 store + query keys
                │     └── F-07
                ├── F-05 layouts + routing
                │     ├── F-07 JoinPage
                │     ├── F-08 StatusPage
                │     ├── F-09 LookupPage
                │     ├── F-10 BoardPage
                │     ├── F-11 LoginPage
                │     ├── F-12 WaitlistPage
                │     ├── F-13 TablesPage
                │     └── F-14 SettingsPage
                └── F-06 shared components
                      ├── F-07
                      ├── F-08
                      ├── F-09
                      ├── F-10
                      ├── F-11
                      ├── F-12
                      ├── F-13
                      └── F-14

Phase 2 (backend + mock DB)
  F-01
    └── B-01 init backend
          ├── B-02 models
          │     ├── B-13 seed
          │     │     ├── B-12 admin reset
          │     │     └── I-02
          │     └── B-14 tests
          ├── B-03 schemas
          ├── B-04 errors + dependencies
          │     ├── B-05 auth
          │     ├── B-06 public
          │     │     └── B-07 staff waitlist
          │     │           └── B-09 dashboard
          │     ├── B-08 staff tables
          │     │     └── B-09 dashboard
          │     ├── B-10 admin settings
          │     ├── B-11 admin tables
          │     └── B-12 admin reset
          └── B-14 tests

Phase 3 (integration)
  B-14, F-15
    └── I-01 switch frontend to real API
          └── I-02 verify end-to-end
                └── D-01

Phase 4 (database)
  I-02
    └── D-01 swap mock store for real DB
          └── D-02 add more tests
                └── D-03 verify all tests pass

2. Recommended Work Order
The order respects dependencies. Do not start an issue before its blockers are done.

Phase 0
P0-01

P0-02

P0-03

P0-04

P0-05

P0-06

P0-07

P0-08

P0-09

P0-10

P0-11

Phase 1
F-01

F-02

F-03

F-04

F-05

F-06

F-07

F-08

F-09

F-10

F-11

F-12

F-13

F-14

F-15

Phase 2
B-01

B-02

B-03

B-04

B-05

B-06

B-07

B-08

B-09

B-10

B-11

B-13

B-12

B-14

Phase 3
I-01

I-02

Phase 4
D-01

D-02

D-03

Total: 45 issues.

3. Labels per Issue
Workflow Labels
All issues start with groomed once PM approves.

groomed

in-progress (set by worker)

blocked (set when waiting on a blocker)

Phase Labels
Issue	Phase Label
P0-*	phase-0-specs
F-*	phase-1-frontend-mock
B-*	phase-2-backend
I-*	phase-3-integration
D-*	phase-4-database
Area Labels
Issue	Area
P0-*	docs
F-01	frontend, docs
F-02 to F-15	frontend
B-01 to B-14	backend
I-01	frontend
I-02	frontend, backend
D-01	database, backend
D-02, D-03	database, backend, test
Type Labels
Issue	Type
P0-01 to P0-11	docs
F-01	chore
F-02	chore
F-03 to F-14	feature
F-15	test
B-01	chore
B-02 to B-13	feature
B-14	test
I-01	chore
I-02	test
D-01	chore
D-02, D-03	test
4. Milestone per Issue
Milestone	Issues
Phase 0 — Specs & Docs	P0-01 to P0-11
Phase 1 — Frontend + Mock	F-01 to F-15
Phase 2 — Backend + Mock DB	B-01 to B-14
Phase 3 — Integration	I-01, I-02
Phase 4 — Database	D-01, D-02, D-03
5. GitHub Metadata Table
Use this table to bulk-create issues.

ID	Title	Labels	Milestone	Deps
P0-01	Write _docs/specs.md	groomed, phase-0-specs, docs	Phase 0	None
P0-02	Write _docs/ui.md	groomed, phase-0-specs, docs	Phase 0	P0-01
P0-03	Write _docs/openapi.yaml	groomed, phase-0-specs, docs	Phase 0	P0-01
P0-04	Write _docs/testing.md	groomed, phase-0-specs, docs	Phase 0	P0-01
P0-05	Write _docs/deployment.md	groomed, phase-0-specs, docs	Phase 0	P0-01
P0-06	Write _docs/api-examples.md	groomed, phase-0-specs, docs	Phase 0	P0-03
P0-07	Write _docs/demo.md	groomed, phase-0-specs, docs	Phase 0	P0-01
P0-08	Write README.md	groomed, phase-0-specs, docs	Phase 0	P0-01, P0-03, P0-05
P0-09	Write CONTRIBUTING.md	groomed, phase-0-specs, docs	Phase 0	P0-01
P0-10	Write AGENTS.md	groomed, phase-0-specs, docs	Phase 0	P0-01, P0-09
P0-11	Write _docs/plan.md	groomed, phase-0-specs, docs	Phase 0	P0-01
F-01	Setup repo structure	groomed, phase-1-frontend-mock, frontend, docs, chore	Phase 1	P0-08, P0-09, P0-10
F-02	Init frontend project	groomed, phase-1-frontend-mock, frontend, chore	Phase 1	F-01
F-03	API client and mock layer	groomed, phase-1-frontend-mock, frontend, feature	Phase 1	F-02
F-04	Zustand store and query keys	groomed, phase-1-frontend-mock, frontend, feature	Phase 1	F-02
F-05	Layouts and routing	groomed, phase-1-frontend-mock, frontend, feature	Phase 1	F-02
F-06	Shared components	groomed, phase-1-frontend-mock, frontend, feature	Phase 1	F-02
F-07	JoinPage	groomed, phase-1-frontend-mock, frontend, feature	Phase 1	F-05, F-06
F-08	StatusPage	groomed, phase-1-frontend-mock, frontend, feature	Phase 1	F-05, F-06
F-09	LookupPage	groomed, phase-1-frontend-mock, frontend, feature	Phase 1	F-05, F-06
F-10	BoardPage	groomed, phase-1-frontend-mock, frontend, feature	Phase 1	F-05, F-06
F-11	LoginPage	groomed, phase-1-frontend-mock, frontend, feature	Phase 1	F-05, F-06
F-12	WaitlistPage	groomed, phase-1-frontend-mock, frontend, feature	Phase 1	F-05, F-06
F-13	TablesPage	groomed, phase-1-frontend-mock, frontend, feature	Phase 1	F-05, F-06
F-14	SettingsPage	groomed, phase-1-frontend-mock, frontend, feature	Phase 1	F-05, F-06
F-15	Frontend tests	groomed, phase-1-frontend-mock, frontend, test	Phase 1	F-03, F-06, F-07, F-08
B-01	Init backend project	groomed, phase-2-backend, backend, chore	Phase 2	F-01
B-02	SQLAlchemy models	groomed, phase-2-backend, backend, feature	Phase 2	B-01
B-03	Pydantic schemas	groomed, phase-2-backend, backend, feature	Phase 2	B-01
B-04	Errors and dependencies	groomed, phase-2-backend, backend, feature	Phase 2	B-01
B-05	Auth endpoints	groomed, phase-2-backend, backend, feature	Phase 2	B-02, B-03, B-04
B-06	Public endpoints	groomed, phase-2-backend, backend, feature	Phase 2	B-02, B-03, B-04
B-07	Staff waitlist endpoints	groomed, phase-2-backend, backend, feature	Phase 2	B-02, B-03, B-04, B-06
B-08	Staff tables endpoints	groomed, phase-2-backend, backend, feature	Phase 2	B-02, B-03, B-04
B-09	Staff dashboard endpoint	groomed, phase-2-backend, backend, feature	Phase 2	B-02, B-03, B-04, B-07, B-08
B-10	Admin settings endpoints	groomed, phase-2-backend, backend, feature	Phase 2	B-02, B-03, B-04
B-11	Admin tables endpoints	groomed, phase-2-backend, backend, feature	Phase 2	B-02, B-03, B-04
B-12	Admin reset endpoint	groomed, phase-2-backend, backend, feature	Phase 2	B-02, B-03, B-04, B-13
B-13	Seed script	groomed, phase-2-backend, backend, feature	Phase 2	B-02
B-14	Backend tests	groomed, phase-2-backend, backend, test	Phase 2	B-05 to B-13
I-01	Switch frontend to real API	groomed, phase-3-integration, frontend, chore	Phase 3	B-14, F-15
I-02	Verify end-to-end flow	groomed, phase-3-integration, frontend, backend, test	Phase 3	I-01
D-01	Swap mock store for real DB	groomed, phase-4-database, database, backend, chore	Phase 4	I-02
D-02	Add more tests	groomed, phase-4-database, database, backend, test	Phase 4	D-01
D-03	Verify all tests pass	groomed, phase-4-database, database, backend, test	Phase 4	D-02
6. Bulk Creation with GitHub CLI
Example command pattern:

bash
gh issue create \
  --title "P0-01 Write _docs/specs.md" \
  --body-file _docs/issues/p0-01.md \
  --label "groomed,phase-0-specs,docs" \
  --milestone "Phase 0 — Specs & Docs"
Create milestones first:

bash
gh milestone create "Phase 0 — Specs & Docs"
gh milestone create "Phase 1 — Frontend + Mock"
gh milestone create "Phase 2 — Backend + Mock DB"
gh milestone create "Phase 3 — Integration"
gh milestone create "Phase 4 — Database"
Create labels first:

bash
gh label create groomed --color 0E8A16
gh label create in-progress --color FBCA04
gh label create blocked --color B60205
gh label create phase-0-specs --color C5DEF5
gh label create phase-1-frontend-mock --color C5DEF5
gh label create phase-2-backend --color C5DEF5
gh label create phase-3-integration --color C5DEF5
gh label create phase-4-database --color C5DEF5
gh label create frontend --color 1D76DB
gh label create backend --color 5319E7
gh label create database --color 006B75
gh label create docs --color 0075CA
gh label create feature --color A2EEEF
gh label create test --color D4C5F9
gh label create chore --color FEF2C0
gh label create bug --color D73A4A
Then create issues in the order listed above.

7. Notes for the Coding Agent
Do not start an issue until its Blocked by issues are closed.

Each issue maps to one branch and one PR.

Use the task template in CONTRIBUTING.md.

Add in-progress when starting.

Add blocked if a dependency is not done.

Close the issue only after the PR is merged.

If an issue is too large in practice, split it and update this plan.

P0-01 Write _docs/specs.md
markdown
## Metadata
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: L
- **Milestone**: Phase 0 — Specs & Docs
- **Labels**: groomed, phase-0-specs, docs

## Goal
Produce the full specification for TableQueue covering roles, flows, state machine, data model, business rules, error codes, API summary, time/timezone, concurrency, security, known limitations, and non-goals.

## Context
- This is the source of truth for all other work.
- Referenced by `AGENTS.md`, `CONTRIBUTING.md`, `_docs/ui.md`, `_docs/openapi.yaml`, `_docs/testing.md`.
- All Phase 0 Q&A decisions must be captured.

## Acceptance criteria
- [ ] File exists at `_docs/specs.md`
- [ ] Contains 21 sections: Overview, Goals and Non-Goals, Roles and Permissions, Core Flows, State Machine, Data Model, Business Rules, Queue Number and Business Date, Table Management, Notifications, Error Codes, API Summary, Time and Timezone, Concurrency, Security and Privacy, Known Limitations, Non-Goals, Environment Variables, Seed Data, Demo Script, Definition of Done
- [ ] All decisions from Phase 0 Q&A are captured
- [ ] All UI text is in English
- [ ] Date format `2026-09-10 21:00`; phone format Taiwan
- [ ] No code

## Test requirements
- [ ] Manual: cross-check against `_docs/plan.md`
- [ ] Manual: cross-check against `AGENTS.md`

## Implementation notes
- Use the draft already produced in Phase 0
- Keep section anchors stable for cross-references
- Do not add features not discussed

## Dependencies
- Blocked by: None
- Blocks: P0-02, P0-03, P0-04, P0-05, P0-07, P0-08, P0-09, P0-10, P0-11

## Out of scope
- Any code
- UI mockups
- OpenAPI definitions

## Constraints
- English only
- File: `_docs/specs.md`
- Do not modify other files

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] PR references this issue
P0-02 Write _docs/ui.md
markdown
## Metadata
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: L
- **Milestone**: Phase 0 — Specs & Docs
- **Labels**: groomed, phase-0-specs, docs

## Goal
Produce the UI guide covering design principles, color tokens, typography, spacing, components, pages, empty/loading/error states, responsive breakpoints, accessibility, motion, sounds, icons, and non-goals.

## Context
- Specs: `_docs/specs.md#1-overview`
- Referenced by all frontend issues.

## Acceptance criteria
- [ ] File exists at `_docs/ui.md`
- [ ] Contains 19 sections: Design Principles, Color Tokens, Typography, Spacing and Radius, Components, Pages, Empty States, Loading States, Error States, Responsive Breakpoints, Accessibility, Motion, Sounds, Icons, Confirm Dialogs, Toast, Dark Mode (non-goal), i18n (non-goal), Component Details
- [ ] Color tokens match `_docs/specs.md`
- [ ] All 8 pages documented
- [ ] All custom components documented
- [ ] All UI text in English

## Test requirements
- [ ] Manual: cross-check against `_docs/specs.md`
- [ ] Manual: cross-check against frontend issues

## Implementation notes
- Dual style: guest warm, staff dense
- No dark mode
- Skeletons over spinners
- Respect `prefers-reduced-motion`

## Dependencies
- Blocked by: P0-01
- Blocks: F-05, F-06, F-07, F-08, F-09, F-10, F-11, F-12, F-13, F-14

## Out of scope
- Code
- Figma files

## Constraints
- English only
- File: `_docs/ui.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] PR references this issue
P0-03 Write _docs/openapi.yaml
markdown
## Metadata
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: L
- **Milestone**: Phase 0 — Specs & Docs
- **Labels**: groomed, phase-0-specs, docs

## Goal
Produce the OpenAPI 3.0.3 contract for all endpoints.

## Context
- Specs: `_docs/specs.md#12-api-summary`
- Referenced by backend issues and frontend API client.

## Acceptance criteria
- [ ] File exists at `_docs/openapi.yaml`
- [ ] `openapi: 3.0.3`
- [ ] `info.title: TableQueue API`, `info.version: 0.1.0`
- [ ] `servers: http://localhost:8000`
- [ ] Tags: `public`, `auth`, `staff`, `admin`, `health`
- [ ] All endpoints from `_docs/specs.md#12-api-summary`
- [ ] All request schemas
- [ ] All response schemas
- [ ] All error responses
- [ ] `components.parameters`: `BranchId`, `QueueNumber`, `Id`
- [ ] `components.responses`: `ValidationError`, `Unauthorized`, `WaitlistNotFound`, `WaitlistInvalidStatus`, `TableNotFound`, `BranchNotFound`, `RateLimited`
- [ ] `components.securitySchemes.bearerAuth`
- [ ] Examples for every endpoint and error code
- [ ] Examples match seed data

## Test requirements
- [ ] Manual: validate with `npx @redocly/cli lint _docs/openapi.yaml`
- [ ] Manual: open in Swagger Editor

## Implementation notes
- snake_case only
- Error shape: `{ error: { code, message, details } }`
- Date format ISO 8601 with timezone
- No camelCase

## Dependencies
- Blocked by: P0-01
- Blocks: P0-06, F-03, B-03, B-05, B-06, B-07, B-08, B-09, B-10, B-11, B-12

## Out of scope
- Implementation

## Constraints
- English only
- File: `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] PR references this issue
P0-04 Write _docs/testing.md
markdown
## Metadata
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: M
- **Milestone**: Phase 0 — Specs & Docs
- **Labels**: groomed, phase-0-specs, docs

## Goal
Produce the testing strategy, test names, fixtures, time injection, coverage goals, non-goals, and commands.

## Context
- Specs: `_docs/specs.md#5-state-machine`, `_docs/specs.md#11-error-codes`
- Referenced by B-14, F-15, D-02.

## Acceptance criteria
- [ ] File exists at `_docs/testing.md`
- [ ] Contains 8 sections: Strategy, Backend Tests, Frontend Tests, Test Data, Time Injection, Coverage Goals, Non-Goals, Commands
- [ ] All backend test names listed
- [ ] All frontend test names listed
- [ ] Fixtures listed
- [ ] Commands documented

## Test requirements
- [ ] Manual: cross-check against `_docs/plan.md`

## Implementation notes
- Backend: pytest + TestClient + in-memory SQLite + freezegun
- Frontend: Vitest + RTL
- No E2E, no concurrency tests

## Dependencies
- Blocked by: P0-01
- Blocks: B-14, F-15, D-02

## Out of scope
- Writing tests

## Constraints
- English only
- File: `_docs/testing.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] PR references this issue
P0-05 Write _docs/deployment.md
markdown
## Metadata
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: M
- **Milestone**: Phase 0 — Specs & Docs
- **Labels**: groomed, phase-0-specs, docs

## Goal
Produce local dev guide, env vars, DB notes, future deployment notes, known limitations, troubleshooting.

## Context
- Specs: `_docs/specs.md#18-environment-variables`
- Referenced by README and B-01.

## Acceptance criteria
- [ ] File exists at `_docs/deployment.md`
- [ ] Contains 6 sections: Local Development, Environment Variables, Database, Future Deployment Notes, Known Limitations, Troubleshooting
- [ ] All backend and frontend env vars documented
- [ ] Local dev commands documented
- [ ] Mobile testing documented
- [ ] CORS documented

## Test requirements
- [ ] Manual: follow local dev steps from clean checkout

## Implementation notes
- No production deployment in v1
- SQLite dev, future PostgreSQL
- No Alembic in v1

## Dependencies
- Blocked by: P0-01
- Blocks: P0-08, B-01

## Out of scope
- Actual deployment

## Constraints
- English only
- File: `_docs/deployment.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] PR references this issue
P0-06 Write _docs/api-examples.md
markdown
## Metadata
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: S
- **Milestone**: Phase 0 — Specs & Docs
- **Labels**: groomed, phase-0-specs, docs

## Goal
Produce curl examples for every endpoint.

## Context
- OpenAPI: `_docs/openapi.yaml`
- Referenced by `_docs/demo.md` and backend issues.

## Acceptance criteria
- [ ] File exists at `_docs/api-examples.md`
- [ ] Every endpoint from `_docs/openapi.yaml` has a curl example
- [ ] Success and error examples included
- [ ] Uses `$TOKEN`, `$ID`, `$TABLE_ID` placeholders
- [ ] Assumes backend at `http://localhost:8000`
- [ ] Assumes branch `1`, PIN `1234`

## Test requirements
- [ ] Manual: run each curl after backend is up

## Implementation notes
- Public, Auth, Staff, Admin, Health sections
- Include error examples

## Dependencies
- Blocked by: P0-03
- Blocks: I-02

## Out of scope
- Code

## Constraints
- English only
- File: `_docs/api-examples.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] PR references this issue
P0-07 Write _docs/demo.md
markdown
## Metadata
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: S
- **Milestone**: Phase 0 — Specs & Docs
- **Labels**: groomed, phase-0-specs, docs

## Goal
Produce step-by-step demo script.

## Context
- Specs: `_docs/specs.md#20-demo-script`
- Referenced by I-02 and README.

## Acceptance criteria
- [ ] File exists at `_docs/demo.md`
- [ ] Prerequisites listed
- [ ] Seed data listed
- [ ] Steps 1–10 included
- [ ] Demo checklist included
- [ ] Uses seed data queue numbers

## Test requirements
- [ ] Manual: follow the script after seed

## Implementation notes
- Steps: Join, Login, Call, Seat, No-show, Board, Settings, Release, Close Day, Reset

## Dependencies
- Blocked by: P0-01
- Blocks: I-02

## Out of scope
- Code

## Constraints
- English only
- File: `_docs/demo.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] PR references this issue
P0-08 Write README.md
markdown
## Metadata
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: M
- **Milestone**: Phase 0 — Specs & Docs
- **Labels**: groomed, phase-0-specs, docs

## Goal
Produce README with overview, tech stack, structure, getting started, env vars, demo, docs links, known limitations.

## Context
- Specs: `_docs/specs.md`
- Deployment: `_docs/deployment.md`
- OpenAPI: `_docs/openapi.yaml`

## Acceptance criteria
- [ ] File exists at repo root
- [ ] Sections: Overview, Tech Stack, Project Structure, Getting Started, Development, Environment Variables, Demo, Documentation, Known Limitations, License
- [ ] Commands match `Makefile`
- [ ] Demo URLs listed
- [ ] Env var tables included
- [ ] Project structure tree included

## Test requirements
- [ ] Manual: follow Getting Started from clean checkout

## Implementation notes
- Keep concise
- Link to `_docs/` for details

## Dependencies
- Blocked by: P0-01, P0-03, P0-05
- Blocks: F-01

## Out of scope
- Code

## Constraints
- English only
- File: `README.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] PR references this issue
P0-09 Write CONTRIBUTING.md
markdown
## Metadata
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: M
- **Milestone**: Phase 0 — Specs & Docs
- **Labels**: groomed, phase-0-specs, docs

## Goal
Produce contribution guide with issue workflow, task template, labels, milestones, branch naming, commit convention, PR flow, testing, DoD, agent rules.

## Context
- Specs: `_docs/specs.md`
- Plan: `_docs/plan.md`

## Acceptance criteria
- [ ] File exists at repo root
- [ ] Sections: Overview, Issue Workflow, Task Template, Labels, Milestones, Branch Naming, Commit Convention, Pull Request, Testing Requirements, Definition of Done, Rules for Coding Agents, File Ownership, Getting Help
- [ ] Task template included
- [ ] All labels listed
- [ ] All milestones listed
- [ ] Branch naming examples
- [ ] Commit convention examples
- [ ] PR template included

## Test requirements
- [ ] Manual: cross-check labels against `_docs/plan.md`

## Implementation notes
- Use the task template from Phase 0
- Include agent rules

## Dependencies
- Blocked by: P0-01
- Blocks: P0-10, F-01

## Out of scope
- Code

## Constraints
- English only
- File: `CONTRIBUTING.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] PR references this issue
P0-10 Write AGENTS.md
markdown
## Metadata
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: M
- **Milestone**: Phase 0 — Specs & Docs
- **Labels**: groomed, phase-0-specs, docs

## Goal
Produce agent guide with hard rules, structure, commands, backend/frontend guidelines, state machine, errors, testing, do-not-do list.

## Context
- Specs: `_docs/specs.md`
- UI: `_docs/ui.md`
- OpenAPI: `_docs/openapi.yaml`
- Testing: `_docs/testing.md`
- Contributing: `CONTRIBUTING.md`

## Acceptance criteria
- [ ] File exists at repo root
- [ ] Sections: What This Project Is, Tech Stack, Read These Files First, Hard Rules, Project Structure, Commands, Backend Guidelines, Frontend Guidelines, UI Rules, State Machine, Time and Timezone, Queue Number, Errors, Testing, Do Not Do, If Stuck, File Ownership
- [ ] All hard rules listed
- [ ] All commands listed
- [ ] Do-not-do list included
- [ ] File ownership table included

## Test requirements
- [ ] Manual: cross-check against `_docs/specs.md`

## Implementation notes
- English only
- Concise but complete

## Dependencies
- Blocked by: P0-01, P0-09
- Blocks: F-01

## Out of scope
- Code

## Constraints
- English only
- File: `AGENTS.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] PR references this issue
P0-11 Write _docs/plan.md
markdown
## Metadata
- **Phase**: phase-0-specs
- **Type**: docs
- **Area**: docs
- **Size**: M
- **Milestone**: Phase 0 — Specs & Docs
- **Labels**: groomed, phase-0-specs, docs

## Goal
Produce this implementation plan with all issues, dependencies, ordering, labels, milestones, and GitHub metadata.

## Context
- All Phase 0 docs
- Referenced by `CONTRIBUTING.md`

## Acceptance criteria
- [ ] File exists at `_docs/plan.md`
- [ ] Index with all 45 issues
- [ ] Phase 0–4 sections
- [ ] Dependency graph
- [ ] Recommended work order
- [ ] Labels per issue
- [ ] Milestone per issue
- [ ] GitHub metadata table
- [ ] Bulk creation commands
- [ ] Notes for coding agent

## Test requirements
- [ ] Manual: cross-check against `CONTRIBUTING.md`

## Implementation notes
- English only
- Keep IDs stable

## Dependencies
- Blocked by: P0-01
- Blocks: None

## Out of scope
- Code

## Constraints
- English only
- File: `_docs/plan.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] PR references this issue

F-01 Setup repo structure
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: chore
- **Area**: frontend, docs
- **Size**: S
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, docs, chore

## Goal
Create the monorepo structure with `backend/`, `frontend/`, `_docs/`, root `package.json`, `Makefile`, `.gitignore`, `.editorconfig`, `.nvmrc`.

## Context
- README: `README.md#project-structure`
- Contributing: `CONTRIBUTING.md`
- Agent guide: `AGENTS.md#5-project-structure`

## Acceptance criteria
- [ ] `backend/` exists with `pyproject.toml` and `app/` folder
- [ ] `frontend/` exists with `package.json` and `src/` folder
- [ ] `_docs/` exists with all spec files
- [ ] Root `package.json` with `concurrently` and scripts: `dev`, `seed`, `test`, `test:backend`, `test:frontend`, `lint`, `format`
- [ ] `Makefile` with targets: `setup`, `dev`, `backend`, `frontend`, `seed`, `test`, `test-backend`, `test-frontend`, `lint`, `format`
- [ ] `.gitignore` includes `node_modules/`, `.venv/`, `__pycache__/`, `dev.db`, `.env`, `dist/`, `coverage/`, `.pytest_cache/`, `.ruff_cache/`, `*.log`
- [ ] `.editorconfig` with Python 4-space, TS/JSON/MD 2-space, LF, UTF-8
- [ ] `.nvmrc` contains `20`
- [ ] `make setup` runs without errors

## Test requirements
- [ ] Manual: `make setup` completes
- [ ] Manual: `make test` runs (may fail if no tests yet)
- [ ] Manual: `make dev` starts both processes

## Implementation notes
- Follow `README.md` project structure exactly
- Use `concurrently` in root `package.json`
- Do not add dependencies beyond `concurrently`
- Keep root `package.json` minimal

## Dependencies
- Blocked by: P0-08, P0-09, P0-10
- Blocks: F-02, B-01

## Out of scope
- Actual backend or frontend code
- Any business logic

## Constraints
- Files: root `package.json`, `Makefile`, `.gitignore`, `.editorconfig`, `.nvmrc`
- Do not modify `_docs/` files
- Do not add features not listed in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `make setup` passes
- [ ] PR references this issue
F-02 Init frontend project
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: chore
- **Area**: frontend
- **Size**: S
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, chore

## Goal
Initialize React + Vite + TypeScript + Tailwind + shadcn/ui frontend.

## Context
- UI: `_docs/ui.md`
- Agent guide: `AGENTS.md#8-frontend-guidelines`

## Acceptance criteria
- [ ] `frontend/package.json` with dependencies from `AGENTS.md#8-frontend-guidelines`
- [ ] `frontend/vite.config.ts` with React plugin, `@` alias, `/api` proxy → `http://localhost:8000`, Vitest config
- [ ] `frontend/tsconfig.json` with `strict: true`, `noUnusedLocals`, `noUnusedParameters`, `@/*` path alias
- [ ] `frontend/tailwind.config.js` with status colors and fonts from `_docs/ui.md#2-color-tokens`
- [ ] `frontend/postcss.config.js`
- [ ] `frontend/index.html` with `TableQueue` title, viewport meta, fonts
- [ ] `frontend/src/main.tsx` with `QueryClientProvider`, `BrowserRouter`, `ErrorBoundary`, `Toaster`
- [ ] `frontend/src/index.css` with Tailwind directives
- [ ] `frontend/.env.example` with all frontend vars
- [ ] `npm run dev` starts without errors
- [ ] `npm run build` succeeds
- [ ] `npm run test` runs (empty ok)

## Test requirements
- [ ] Manual: `npm run dev` opens `http://localhost:5173`
- [ ] Manual: `npm run build` succeeds

## Implementation notes
- React 18, Vite 6, Tailwind 3, shadcn/ui
- No dark mode
- All UI text in English
- Fonts: Inter + Noto Sans TC
- `DEV` badge only when `import.meta.env.DEV`

## Dependencies
- Blocked by: F-01
- Blocks: F-03, F-04, F-05, F-06

## Out of scope
- Pages
- API client
- Mock data
- Components

## Constraints
- Files: `frontend/`
- Do not add features not listed in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-03 API client and mock layer
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, feature

## Goal
Create centralized API client and mock layer for frontend.

## Context
- Agent guide: `AGENTS.md#8-frontend-guidelines`
- OpenAPI: `_docs/openapi.yaml`
- Error codes: `_docs/specs.md#11-error-codes`

## Acceptance criteria
- [ ] `frontend/src/api/client.ts` with:
  - Base URL from `VITE_API_BASE_URL` (fallback `/api/v1`)
  - Authorization header from `staffStore.token`
  - 30s timeout with `AbortController`
  - 204 returns `null`
  - 401 → clear token, clear query cache, redirect to `/staff/login`
  - 429 → toast `Too many requests. Please try again later.`
  - 5xx → toast `Something went wrong. Please try again.`
  - Network error → `NETWORK_ERROR`
- [ ] `frontend/src/api/errors.ts` with `ApiError` class and `getErrorMessage(code)` mapping all codes from `_docs/specs.md#11-error-codes`
- [ ] `frontend/src/api/queryKeys.ts` with all keys
- [ ] `frontend/src/api/mock/` with mock responses matching `_docs/openapi.yaml`
- [ ] `frontend/src/api/mock/seed.ts` with mock data matching `_docs/specs.md#19-seed-data`
- [ ] `VITE_USE_MOCK=true` uses mock, `false` uses real API
- [ ] Endpoint functions: `joinWaitlist`, `getStatus`, `cancelWaitlist`, `getPublicBranch`, `getBoard`, `login`, `changePin`, `listWaitlist`, `callWaitlist`, `seatWaitlist`, `noShowWaitlist`, `restoreWaitlist`, `revertWaitlist`, `cancelWaitlistByStaff`, `editWaitlist`, `reorderWaitlist`, `listTables`, `updateTableStatus`, `releaseTable`, `getDashboard`, `getSettings`, `updateSettings`, `listAdminTables`, `createTable`, `updateTable`, `deleteTable`, `resetData`

## Test requirements
- [ ] Frontend: `src/api/client.test.ts::adds Authorization header`
- [ ] Frontend: `src/api/client.test.ts::parses error code`
- [ ] Frontend: `src/api/client.test.ts::returns null on 204`
- [ ] Frontend: `src/api/client.test.ts::handles network error`
- [ ] Frontend: `src/api/errors.test.ts::maps known codes`
- [ ] Frontend: `src/api/errors.test.ts::falls back to generic message`

## Implementation notes
- All backend calls go through `api/client.ts`
- Components never fetch directly
- Mock uses same shapes as OpenAPI
- Use `staffStore` for token
- Mock data must match seed data

## Dependencies
- Blocked by: F-02
- Blocks: F-15, I-01

## Out of scope
- Pages
- Components

## Constraints
- Files: `frontend/src/api/`
- Do not add endpoints not in `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-04 Zustand store and query keys
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: S
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, feature

## Goal
Create `staffStore` with Zustand and centralized query keys.

## Context
- Agent guide: `AGENTS.md#8-frontend-guidelines`

## Acceptance criteria
- [ ] `frontend/src/stores/staffStore.ts` with:
  - `token: string | null`
  - `soundEnabled: boolean`
  - `setToken(token)`
  - `logout()`
  - `setSoundEnabled(enabled)`
  - `persist` middleware with `partialize` persisting only `token` and `soundEnabled`
  - Storage key `staff-storage`
- [ ] `frontend/src/api/queryKeys.ts` with:
  - `waitlist(branchId)`
  - `waitlistStatus(branchId, queueNumber)`
  - `tables(branchId)`
  - `dashboard(branchId)`
  - `settings(branchId)`
  - `publicBranch(branchId)`
  - `board(branchId)`

## Test requirements
- [ ] Frontend: `src/stores/staffStore.test.ts::sets token`
- [ ] Frontend: `src/stores/staffStore.test.ts::logout clears token`
- [ ] Frontend: `src/stores/staffStore.test.ts::persists token`
- [ ] Frontend: `src/stores/staffStore.test.ts::persists soundEnabled`

## Implementation notes
- Zustand v5
- Only `token` and `soundEnabled` persisted
- Query keys are `as const`

## Dependencies
- Blocked by: F-02
- Blocks: F-03, F-11

## Out of scope
- Pages
- Components

## Constraints
- Files: `frontend/src/stores/staffStore.ts`, `frontend/src/api/queryKeys.ts`
- Do not add state not in `AGENTS.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-05 Layouts and routing
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, feature

## Goal
Create `PublicLayout`, `StaffLayout`, routing, `routes.ts`, `NotFoundPage`, `DevBadge`.

## Context
- UI: `_docs/ui.md#6-pages`
- Agent guide: `AGENTS.md#8-frontend-guidelines`

## Acceptance criteria
- [ ] `frontend/src/routes.ts` with all route constants
- [ ] `frontend/src/App.tsx` with all routes:
  - `/join`
  - `/status/:queueNumber`
  - `/lookup`
  - `/board/:branchId`
  - `/staff/login`
  - `/staff/waitlist`
  - `/staff/tables`
  - `/admin/settings`
  - `*` → `NotFoundPage`
- [ ] `frontend/src/layouts/PublicLayout.tsx` with header (`TableQueue` + subtitle), footer, `DevBadge`, background `#FFFBF5`
- [ ] `frontend/src/layouts/StaffLayout.tsx` with nav (Waitlist, Tables, Settings), logout, `DevBadge`, background `#F8FAFC`, token check redirect
- [ ] `frontend/src/pages/NotFoundPage.tsx` with `Page not found.` and `Go home` button
- [ ] `frontend/src/components/DevBadge.tsx` only when `import.meta.env.DEV`
- [ ] All UI text in English

## Test requirements
- [ ] Frontend: `src/layouts/StaffLayout.test.tsx::redirects when no token`
- [ ] Frontend: `src/pages/NotFoundPage.test.tsx::renders message`
- [ ] Frontend: `src/components/DevBadge.test.tsx::hides in production`

## Implementation notes
- React Router v6
- No nested routes beyond two layouts
- `DevBadge` fixed top-right

## Dependencies
- Blocked by: F-02
- Blocks: F-07, F-08, F-09, F-10, F-11, F-12, F-13, F-14

## Out of scope
- Actual page content

## Constraints
- Files: `frontend/src/layouts/`, `frontend/src/App.tsx`, `frontend/src/routes.ts`, `frontend/src/pages/NotFoundPage.tsx`, `frontend/src/components/DevBadge.tsx`
- Do not add routes not in `_docs/ui.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-06 Shared components
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, feature

## Goal
Create shared UI components used across pages.

## Context
- UI: `_docs/ui.md#5-components`, `_docs/ui.md#19-component-details`
- Agent guide: `AGENTS.md#8-frontend-guidelines`

## Acceptance criteria
- [ ] `frontend/src/components/StatusBadge.tsx` with all statuses
- [ ] `frontend/src/components/Countdown.tsx` with `mm:ss` and red at zero
- [ ] `frontend/src/components/WaitlistCard.tsx` with actions
- [ ] `frontend/src/components/TableCard.tsx` with occupied info
- [ ] `frontend/src/components/EmptyState.tsx` with `icon`, `title`, `description`, `action`
- [ ] `frontend/src/components/LoadingSkeleton.tsx` with `variant` and `count`
- [ ] `frontend/src/components/ConfirmDialog.tsx` with `variant` and `onConfirm`
- [ ] `frontend/src/components/ConnectionBanner.tsx` with 3-failure threshold
- [ ] `frontend/src/components/SoundToggle.tsx` with `staffStore.soundEnabled`
- [ ] `frontend/src/components/QrCode.tsx` using `qrcode.react`
- [ ] `frontend/src/hooks/useCountdown.ts` with `remainingSeconds` and `onComplete`
- [ ] All components match `_docs/ui.md`
- [ ] All icon buttons have `aria-label`
- [ ] All UI text in English

## Test requirements
- [ ] Frontend: `src/components/StatusBadge.test.tsx::renders all statuses`
- [ ] Frontend: `src/components/Countdown.test.tsx::renders mm:ss`
- [ ] Frontend: `src/components/Countdown.test.tsx::turns red at zero`
- [ ] Frontend: `src/components/Countdown.test.tsx::calls onComplete`
- [ ] Frontend: `src/components/WaitlistCard.test.tsx::renders entry`
- [ ] Frontend: `src/components/TableCard.test.tsx::renders occupied`
- [ ] Frontend: `src/hooks/useCountdown.test.ts::ticks every second`

## Implementation notes
- Use shadcn/ui primitives
- Use `lucide-react` icons
- Use `qrcode.react` for QR code
- `useCountdown` clears interval on unmount
- `ConnectionBanner` does not block interaction

## Dependencies
- Blocked by: F-02
- Blocks: F-07, F-08, F-09, F-10, F-11, F-12, F-13, F-14

## Out of scope
- Pages

## Constraints
- Files: `frontend/src/components/`, `frontend/src/hooks/useCountdown.ts`
- Do not add components not in `_docs/ui.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-07 JoinPage
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, feature

## Goal
Build `/join` page.

## Context
- UI: `_docs/ui.md#61-join--join-page`
- OpenAPI: `getPublicBranch`, `joinWaitlist`
- Specs: `_docs/specs.md#7-business-rules`

## Acceptance criteria
- [ ] Reads `branch` query, falls back to `VITE_BRANCH_ID`
- [ ] Calls `usePublicBranch`
- [ ] Shows restaurant name, branch name, hours, waiting count
- [ ] Shows closed message when `is_waitlist_open=false`
- [ ] Form fields: name, phone, party size, note (optional)
- [ ] Validates:
  - Name: 1–50 chars
  - Phone: Taiwan mobile `09xx-xxx-xxx` or landline `02-xxxx-xxxx`
  - Party size: 1–20
  - Note: 0–200 chars
- [ ] On success: navigate to `/status/{queueNumber}?token={statusToken}`
- [ ] On duplicate phone: show `This phone number is already on the waitlist.` and `View Status` button → `/lookup`
- [ ] On `WAITLIST_CLOSED`: show closed message
- [ ] On `BRANCH_NOT_FOUND`: show `This branch is not available.`
- [ ] All UI text in English
- [ ] Date format `2026-09-10 21:00`; phone format Taiwan

## Test requirements
- [ ] Frontend: `src/pages/JoinPage.test.tsx::renders form when open`
- [ ] Frontend: `src/pages/JoinPage.test.tsx::shows closed message`
- [ ] Frontend: `src/pages/JoinPage.test.tsx::validates required fields`
- [ ] Frontend: `src/pages/JoinPage.test.tsx::validates phone format`
- [ ] Frontend: `src/pages/JoinPage.test.tsx::shows duplicate phone error`

## Implementation notes
- `react-hook-form` + `zod`
- Validate on blur, re-validate on change
- Disable submit while pending
- Mobile-first, `max-w-md`

## Dependencies
- Blocked by: F-05, F-06
- Blocks: F-15, I-02

## Out of scope
- Backend
- Real API

## Constraints
- Files: `frontend/src/pages/public/JoinPage.tsx`
- Do not add features not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-08 StatusPage
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, feature

## Goal
Build `/status/:queueNumber` page.

## Context
- UI: `_docs/ui.md#62-status-queueNumber--status-page`
- OpenAPI: `getWaitlistStatus`, `cancelWaitlist`
- Specs: `_docs/specs.md#5-state-machine`

## Acceptance criteria
- [ ] Reads `token` from query; if missing, shows last-3-digits form
- [ ] Calls `useStatus`
- [ ] Progress bar: `Waiting → Called → Seated`
- [ ] Shows queue number in `text-5xl`
- [ ] Shows `N groups ahead` and `Estimated wait: X min`
- [ ] `WAITING`: blue, `Cancel` button
- [ ] `CALLED`: orange, countdown `mm:ss`, vibration, sound toggle, `Cancel` with confirm
- [ ] `SEATED`: `You're seated. Enjoy your meal!`
- [ ] `NO_SHOW`: red
- [ ] `CANCELLED`: grey, `Join Again` button
- [ ] Polls every 5s, refetch on focus, refetch at countdown 0
- [ ] Sound requires user interaction; shows `Tap to enable sound` if not enabled
- [ ] All UI text in English

## Test requirements
- [ ] Frontend: `src/pages/StatusPage.test.tsx::renders waiting state`
- [ ] Frontend: `src/pages/StatusPage.test.tsx::renders called state with countdown`
- [ ] Frontend: `src/pages/StatusPage.test.tsx::renders seated message`
- [ ] Frontend: `src/pages/StatusPage.test.tsx::renders cancelled with join again`

## Implementation notes
- Use `useCountdown` and `Countdown`
- Use `queryKeys.waitlistStatus`
- Do not compute time on frontend; use `remaining_seconds`
- `aria-live="polite"` on `StatusBadge`, `aria-live="off"` on `Countdown`

## Dependencies
- Blocked by: F-05, F-06
- Blocks: F-15, I-02

## Out of scope
- Backend
- Real API

## Constraints
- Files: `frontend/src/pages/public/StatusPage.tsx`
- Do not add features not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-09 LookupPage
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: S
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, feature

## Goal
Build `/lookup` page.

## Context
- UI: `_docs/ui.md#63-lookup--lookup-page`
- OpenAPI: `getWaitlistStatus`

## Acceptance criteria
- [ ] Fields: queue number, last 3 digits of phone
- [ ] Queue number auto-uppercase
- [ ] Last 3 digits `inputMode="numeric"`, `maxLength=3`
- [ ] Submit: `Look Up Status`
- [ ] On success: navigate to `/status/{queueNumber}?token={statusToken}`
- [ ] On failure: `No matching waitlist entry found.`
- [ ] Mobile-first, `max-w-md`
- [ ] All UI text in English

## Test requirements
- [ ] Frontend: `src/pages/LookupPage.test.tsx::submits valid input`
- [ ] Frontend: `src/pages/LookupPage.test.tsx::shows error on failure`

## Implementation notes
- `react-hook-form` + `zod`
- No polling on this page

## Dependencies
- Blocked by: F-05, F-06
- Blocks: I-02

## Out of scope
- Backend
- Real API

## Constraints
- Files: `frontend/src/pages/public/LookupPage.tsx`
- Do not add features not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-10 BoardPage
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, feature

## Goal
Build `/board/:branchId` public board.

## Context
- UI: `_docs/ui.md#64-board-branchId--public-board`
- OpenAPI: `getPublicBoard`

## Acceptance criteria
- [ ] Reads `branchId` from path
- [ ] Calls `useBoard`
- [ ] Shows restaurant name, branch, hours, waitlist status
- [ ] Shows `Now Serving: A012`
- [ ] Shows `Next up: A013`
- [ ] Shows `Recent calls` (max 3)
- [ ] Shows `Waiting: N`
- [ ] QR code with `{publicBaseUrl}/join?branch={branchId}`
- [ ] QR code label: `Scan to join the waitlist`
- [ ] Polls every 5s
- [ ] Never shows names or phones
- [ ] Mobile: single column; desktop: two columns
- [ ] All UI text in English

## Test requirements
- [ ] Frontend: `src/pages/BoardPage.test.tsx::renders current call`
- [ ] Frontend: `src/pages/BoardPage.test.tsx::renders empty state`

## Implementation notes
- Use `QrCode` component
- Use `getPublicBaseUrl()` from `lib/publicBaseUrl.ts`
- `is_waitlist_open=false` shows `Waitlist is currently closed.`

## Dependencies
- Blocked by: F-05, F-06
- Blocks: I-02

## Out of scope
- Backend
- Real API

## Constraints
- Files: `frontend/src/pages/public/BoardPage.tsx`
- Do not add features not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-11 LoginPage
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: S
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, feature

## Goal
Build `/staff/login` page.

## Context
- UI: `_docs/ui.md#65-stafflogin--login-page`
- OpenAPI: `staffLogin`

## Acceptance criteria
- [ ] Single PIN input (`type=password`, `inputMode=numeric`)
- [ ] `Remember me` checkbox (default checked)
- [ ] `Login` button
- [ ] Error: `Invalid PIN.`
- [ ] On success: store token, navigate to `/staff/waitlist`
- [ ] Redirect to `/staff/waitlist` if already logged in
- [ ] `Remember me` checked → localStorage; unchecked → sessionStorage
- [ ] `AUTH_RATE_LIMITED` shows `Too many attempts. Please try again later.`
- [ ] Centered `max-w-sm`
- [ ] All UI text in English

## Test requirements
- [ ] Frontend: `src/pages/LoginPage.test.tsx::submits PIN`
- [ ] Frontend: `src/pages/LoginPage.test.tsx::shows invalid PIN error`
- [ ] Frontend: `src/pages/LoginPage.test.tsx::redirects when logged in`

## Implementation notes
- Use `staffStore.setToken`
- Use `api/auth.ts::login`

## Dependencies
- Blocked by: F-04, F-05, F-06
- Blocks: I-02

## Out of scope
- Backend
- Real API

## Constraints
- Files: `frontend/src/pages/staff/LoginPage.tsx`
- Do not add features not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-12 WaitlistPage
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: L
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, feature

## Goal
Build `/staff/waitlist` page.

## Context
- UI: `_docs/ui.md#66-staffwaitlist--waitlist-page`
- OpenAPI: `listWaitlist`, `callWaitlist`, `seatWaitlist`, `noShowWaitlist`, `restoreWaitlist`, `revertWaitlist`, `cancelWaitlistByStaff`, `editWaitlist`, `reorderWaitlist`, `getDashboard`, `updateSettings`

## Acceptance criteria
- [ ] Stats cards: Waiting, Called, Seated, Available Tables, Occupied, Cleaning, No-show today, Cancelled today, Seated today, Avg wait today
- [ ] Search box: name or phone last 3 digits (debounced 300ms)
- [ ] Status filter: `Active` / `Closed` / `All`
- [ ] Party size filter
- [ ] `Pause Waitlist` switch
- [ ] `Close Day` button with confirmation
- [ ] List with cards sorted by `sort_order`
- [ ] Card actions: `Call`, `Seat`, `No-show`, `Restore`, `Revert`, `Cancel`, `Edit`
- [ ] `CALLED` cards show countdown
- [ ] Up/down reorder buttons in v1
- [ ] Collapsible `Closed today` section
- [ ] `Last updated: HH:MM:SS`
- [ ] Polls every 3s
- [ ] Confirmation dialogs for destructive actions
- [ ] All UI text in English

## Test requirements
- [ ] Frontend: `src/pages/WaitlistPage.test.tsx::renders list`
- [ ] Frontend: `src/pages/WaitlistPage.test.tsx::filters by status`
- [ ] Frontend: `src/pages/WaitlistPage.test.tsx::searches by name`
- [ ] Frontend: `src/pages/WaitlistPage.test.tsx::calls entry`
- [ ] Frontend: `src/pages/WaitlistPage.test.tsx::opens seat dialog`

## Implementation notes
- Use `useWaitlist`, `useDashboard`
- Use `WaitlistCard`, `ConfirmDialog`, `EmptyState`, `LoadingSkeleton`
- Invalidate `waitlist`, `dashboard`, `tables` after mutations

## Dependencies
- Blocked by: F-05, F-06
- Blocks: I-02

## Out of scope
- Backend
- Real API
- Drag-and-drop

## Constraints
- Files: `frontend/src/pages/staff/WaitlistPage.tsx`
- Do not add features not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-13 TablesPage
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: M
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, feature

## Goal
Build `/staff/tables` page.

## Context
- UI: `_docs/ui.md#67-stafftables--tables-page`
- OpenAPI: `listTables`, `updateTableStatus`, `releaseTable`

## Acceptance criteria
- [ ] Grid: `grid-cols-2 md:grid-cols-3 lg:grid-cols-4`
- [ ] Cards show label, capacity, status color
- [ ] `AVAILABLE` → click to mark `CLEANING`
- [ ] `CLEANING` → click to mark `AVAILABLE`
- [ ] `OCCUPIED` shows `A012 · 4 pax · 25 min` and `Release Table` button
- [ ] `Release Table` confirmation
- [ ] Empty state: `No tables yet. Add tables in Settings.`
- [ ] Polls every 5s
- [ ] All UI text in English

## Test requirements
- [ ] Frontend: `src/pages/TablesPage.test.tsx::renders tables`
- [ ] Frontend: `src/pages/TablesPage.test.tsx::toggles cleaning`
- [ ] Frontend: `src/pages/TablesPage.test.tsx::releases occupied`

## Implementation notes
- Use `useTables`
- Use `TableCard`, `ConfirmDialog`, `EmptyState`
- Invalidate `tables`, `dashboard`, `waitlist` after mutations

## Dependencies
- Blocked by: F-05, F-06
- Blocks: I-02

## Out of scope
- Backend
- Real API
- Drag-and-drop
- Seating from this page

## Constraints
- Files: `frontend/src/pages/staff/TablesPage.tsx`
- Do not add features not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-14 SettingsPage
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: feature
- **Area**: frontend
- **Size**: L
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, feature

## Goal
Build `/admin/settings` page.

## Context
- UI: `_docs/ui.md#68-adminsettings--settings-page`
- OpenAPI: `getSettings`, `updateSettings`, `listAdminTables`, `createTable`, `updateTable`, `deleteTable`, `changePin`, `resetData`

## Acceptance criteria
- [ ] Sections:
  1. Store Info: name, address, phone, open time, close time
  2. Waitlist Settings: hold minutes, avg seat minutes, queue prefix, waitlist open switch
  3. Tables: list with edit/delete, add table form
  4. Notifications & Sound: templates, sound default
  5. Danger Zone: change PIN, reset data (dev only)
- [ ] Each section has its own `Save` button
- [ ] Range hints: `hold_minutes 5–15`, `avg_seat_minutes 5–60`
- [ ] Table CRUD with confirmation on delete
- [ ] Change PIN form: current, new, confirm
- [ ] Reset Data requires typing `RESET`, only when `import.meta.env.DEV`
- [ ] `max-w-4xl`
- [ ] All UI text in English

## Test requirements
- [ ] Frontend: `src/pages/SettingsPage.test.tsx::renders sections`
- [ ] Frontend: `src/pages/SettingsPage.test.tsx::updates settings`
- [ ] Frontend: `src/pages/SettingsPage.test.tsx::creates table`
- [ ] Frontend: `src/pages/SettingsPage.test.tsx::changes PIN`

## Implementation notes
- Use `useSettings`
- Invalidate `settings`, `publicBranch`, `tables` after mutations
- Use `ConfirmDialog` for destructive actions

## Dependencies
- Blocked by: F-05, F-06
- Blocks: I-02

## Out of scope
- Backend
- Real API

## Constraints
- Files: `frontend/src/pages/admin/SettingsPage.tsx`
- Do not add features not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue
F-15 Frontend tests
markdown
## Metadata
- **Phase**: phase-1-frontend-mock
- **Type**: test
- **Area**: frontend
- **Size**: M
- **Milestone**: Phase 1 — Frontend + Mock
- **Labels**: groomed, phase-1-frontend-mock, frontend, test

## Goal
Add Vitest + RTL tests for API client and key components/pages.

## Context
- Testing: `_docs/testing.md#3-frontend-tests`

## Acceptance criteria
- [ ] `src/api/client.test.ts`
- [ ] `src/api/errors.test.ts`
- [ ] `src/stores/staffStore.test.ts`
- [ ] `src/hooks/useCountdown.test.ts`
- [ ] `src/components/StatusBadge.test.tsx`
- [ ] `src/components/Countdown.test.tsx`
- [ ] `src/components/WaitlistCard.test.tsx`
- [ ] `src/components/TableCard.test.tsx`
- [ ] `src/components/DevBadge.test.tsx`
- [ ] `src/pages/JoinPage.test.tsx`
- [ ] `src/pages/StatusPage.test.tsx`
- [ ] `src/pages/LookupPage.test.tsx`
- [ ] `src/pages/BoardPage.test.tsx`
- [ ] `src/pages/LoginPage.test.tsx`
- [ ] `src/pages/WaitlistPage.test.tsx`
- [ ] `src/pages/TablesPage.test.tsx`
- [ ] `src/pages/SettingsPage.test.tsx`
- [ ] `src/layouts/StaffLayout.test.tsx`
- [ ] `src/pages/NotFoundPage.test.tsx`
- [ ] `src/test/setup.ts` with `@testing-library/jest-dom`
- [ ] `src/test/fixtures.ts` with `mockWaitlistEntry`, `mockTable`, `mockBranch`, `mockDashboard`, `mockBoard`
- [ ] `npm run test` passes
- [ ] Coverage ≥ 70% on API client and components

## Test requirements
- [ ] All files above created and passing

## Implementation notes
- Vitest + jsdom
- `@testing-library/react` + `@testing-library/jest-dom`
- Fixtures match `_docs/openapi.yaml`
- Use `vi.useFakeTimers()` for countdown tests

## Dependencies
- Blocked by: F-03, F-06, F-07, F-08
- Blocks: I-01

## Out of scope
- Playwright E2E
- Visual regression tests

## Constraints
- Files: `frontend/src/**/*.test.tsx`, `frontend/src/**/*.test.ts`, `frontend/src/test/`
- Do not add features not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] PR references this issue

B-01 Init backend project
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: chore
- **Area**: backend
- **Size**: S
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, chore

## Goal
Initialize FastAPI backend with uv, SQLAlchemy 2.0, Pydantic v2, config, health endpoint.

## Context
- Specs: `_docs/specs.md#6-data-model`, `_docs/specs.md#18-environment-variables`
- Agent guide: `AGENTS.md#7-backend-guidelines`
- Deployment: `_docs/deployment.md#2-environment-variables`

## Acceptance criteria
- [ ] `backend/pyproject.toml` with dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy>=2.0`, `pydantic>=2.0`, `pydantic-settings`, `passlib[bcrypt]`, `python-jose[cryptography]`, `slowapi`, `python-multipart`, and dev deps `pytest`, `httpx`, `freezegun`
- [ ] `backend/.env.example` with all backend vars
- [ ] `backend/app/main.py` with FastAPI app and `lifespan`
- [ ] `backend/app/config.py` with `pydantic-settings` reading env
- [ ] `backend/app/database.py` with SQLAlchemy engine, `SessionLocal`, `Base`
- [ ] `backend/app/__init__.py`
- [ ] `GET /health` returns `{ status, version, env }`
- [ ] `uv run uvicorn app.main:app --reload` starts without errors
- [ ] Swagger UI shows `/health`
- [ ] Startup creates default Restaurant, Branch, Settings if missing
- [ ] `ruff` config in `pyproject.toml`
- [ ] Startup validates required env vars, fails fast if missing

## Test requirements
- [ ] Backend: `tests/test_health.py::test_health_ok`
- [ ] Backend: `tests/test_health.py::test_health_env`
- [ ] Manual: `curl http://localhost:8000/health`

## Implementation notes
- Python 3.11+
- SQLAlchemy 2.0 style
- Pydantic v2
- No Alembic in v1
- `create_all` on startup
- `ENV` drives `development` / `test` / `production`
- Never log secrets

## Dependencies
- Blocked by: F-01
- Blocks: B-02, B-03, B-04

## Out of scope
- Business logic
- Endpoints beyond `/health`

## Constraints
- Files: `backend/`
- Do not add features not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-02 SQLAlchemy models
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, feature

## Goal
Create SQLAlchemy 2.0 models for Restaurant, Branch, Table, WaitlistEntry, Settings.

## Context
- Specs: `_docs/specs.md#6-data-model`
- Agent guide: `AGENTS.md#7-backend-guidelines`

## Acceptance criteria
- [ ] `backend/app/models.py` with 5 models
- [ ] All fields match `_docs/specs.md#6-data-model`
- [ ] Enums: `WaitlistStatus`, `TableStatus`, `WaitlistSource`, `CancelledReason`
- [ ] Unique constraints:
  - `(branch_id, business_date, queue_prefix, seq)` on WaitlistEntry
  - `(branch_id, label)` on Table
  - `branch_id` on Settings
- [ ] Indexes:
  - `(branch_id, business_date, status)` on WaitlistEntry
  - `(branch_id, sort_order)` on WaitlistEntry
  - `(branch_id, is_active, status)` on Table
- [ ] Foreign keys per spec
- [ ] `created_at` and `updated_at` use Python `datetime.now(timezone.utc)`
- [ ] `onupdate` uses Python function
- [ ] `Base.metadata.create_all` creates all tables

## Test requirements
- [ ] Backend: `tests/test_models.py::test_create_all`
- [ ] Backend: `tests/test_models.py::test_unique_queue_number`
- [ ] Backend: `tests/test_models.py::test_unique_table_label`
- [ ] Backend: `tests/test_models.py::test_settings_unique_branch`
- [ ] Backend: `tests/test_models.py::test_foreign_keys`

## Implementation notes
- SQLAlchemy 2.0 style with `Mapped[]` and `mapped_column()`
- No `datetime.utcnow()`
- UUID PK for Table and WaitlistEntry
- Integer PK for Restaurant, Branch, Settings
- No `ON DELETE CASCADE` in v1

## Dependencies
- Blocked by: B-01
- Blocks: B-03, B-13, B-14

## Out of scope
- Schemas
- Endpoints
- Business logic

## Constraints
- Files: `backend/app/models.py`
- Do not add fields not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-03 Pydantic schemas
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, feature

## Goal
Create Pydantic v2 request and response schemas matching `_docs/openapi.yaml`.

## Context
- OpenAPI: `_docs/openapi.yaml#components-schemas`
- Specs: `_docs/specs.md#7-business-rules`

## Acceptance criteria
- [ ] `backend/app/schemas.py` with all schemas
- [ ] Request schemas:
  - `JoinWaitlistRequest`
  - `CancelWaitlistRequest`
  - `StaffLoginRequest`
  - `ChangePinRequest`
  - `SeatWaitlistRequest`
  - `EditWaitlistRequest`
  - `ReorderWaitlistRequest`
  - `UpdateTableStatusRequest`
  - `CreateTableRequest`
  - `UpdateTableRequest`
  - `UpdateSettingsRequest`
  - `ResetDataRequest`
- [ ] Response schemas:
  - `WaitlistEntryResponse`
  - `WaitlistListResponse`
  - `WaitlistStatusResponse`
  - `TableResponse`
  - `TableListResponse`
  - `DashboardResponse`
  - `SettingsResponse`
  - `PublicBranchResponse`
  - `BoardResponse`
  - `HealthResponse`
  - `ErrorResponse`
  - `StaffLoginResponse`
- [ ] Request and response are separate classes
- [ ] `model_config = ConfigDict(from_attributes=True)` on response schemas
- [ ] Validation matches `_docs/specs.md#7-business-rules`
- [ ] Phone regex Taiwan format
- [ ] `queue_prefix` regex `^[A-Z]{1,3}$`
- [ ] `open_time`, `close_time` regex `^\d{2}:\d{2}$`
- [ ] Party size 1–20
- [ ] Note max 200 chars
- [ ] Name 1–50 chars

## Test requirements
- [ ] Backend: `tests/test_schemas.py::test_join_waitlist_validation`
- [ ] Backend: `tests/test_schemas.py::test_party_size_range`
- [ ] Backend: `tests/test_schemas.py::test_change_pin_mismatch`
- [ ] Backend: `tests/test_schemas.py::test_note_max_length`
- [ ] Backend: `tests/test_schemas.py::test_queue_prefix_format`
- [ ] Backend: `tests/test_schemas.py::test_open_time_format`

## Implementation notes
- Pydantic v2
- Use `Field` for constraints
- Use `field_validator` where needed
- snake_case only
- No camelCase

## Dependencies
- Blocked by: B-01
- Blocks: B-05, B-06, B-07, B-08, B-09, B-10, B-11, B-12

## Out of scope
- Endpoints
- Business logic

## Constraints
- Files: `backend/app/schemas.py`
- Do not add fields not in `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-04 Errors and dependencies
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, feature

## Goal
Create `AppError`, global exception handlers, and FastAPI dependencies.

## Context
- Specs: `_docs/specs.md#11-error-codes`
- Agent guide: `AGENTS.md#7-backend-guidelines`

## Acceptance criteria
- [ ] `backend/app/errors.py` with `AppError(code, status_code, details)`
- [ ] Exception handlers for:
  - `AppError` → JSON with `error.code`, `error.message`, `error.details`
  - `RequestValidationError` → `VALIDATION_ERROR` with `details.fields`
  - `Exception` → `INTERNAL_ERROR`, no stack trace
- [ ] `backend/app/dependencies.py` with:
  - `get_db()` yielding session, closing after
  - `get_current_staff()` decoding JWT, raising `AUTH_TOKEN_EXPIRED`
  - `get_now()` returning `datetime.now(timezone.utc)`
- [ ] `HTTPBearer` security scheme
- [ ] All error codes from `_docs/specs.md#11-error-codes` defined
- [ ] Request ID middleware generating `uuid4` and returning `X-Request-ID`
- [ ] Security headers middleware: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- [ ] CORS middleware reading `CORS_ORIGINS`
- [ ] `slowapi` limiter configured

## Test requirements
- [ ] Backend: `tests/test_errors.py::test_app_error_handler`
- [ ] Backend: `tests/test_errors.py::test_validation_error_handler`
- [ ] Backend: `tests/test_errors.py::test_get_current_staff_invalid`
- [ ] Backend: `tests/test_errors.py::test_internal_error_no_stack`
- [ ] Backend: `tests/test_errors.py::test_request_id_header`
- [ ] Backend: `tests/test_errors.py::test_security_headers`

## Implementation notes
- Routers do not catch; raise `AppError`
- Never log phone, name, token
- Never expose stack trace
- CORS `allow_credentials=False`

## Dependencies
- Blocked by: B-01
- Blocks: B-05, B-06, B-07, B-08, B-09, B-10, B-11, B-12

## Out of scope
- Endpoints
- Business logic

## Constraints
- Files: `backend/app/errors.py`, `backend/app/dependencies.py`, `backend/app/main.py`
- Do not add error codes not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-05 Auth endpoints
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, feature

## Goal
Implement `POST /api/v1/auth/login` and `POST /api/v1/auth/change-pin`.

## Context
- OpenAPI: `staffLogin`, `changePin`
- Specs: `_docs/specs.md#3-roles-and-permissions`

## Acceptance criteria
- [ ] `POST /api/v1/auth/login` validates PIN against `Settings.staff_pin_hash`, fallback to `STAFF_PIN`
- [ ] Returns JWT with `sub=staff`, `role=staff`, `iat`, `exp`
- [ ] `expires_in` in seconds
- [ ] Rate limit: 5/minute per IP
- [ ] `POST /api/v1/auth/change-pin` validates current, new, confirm; new ≠ current
- [ ] New PIN 4–6 digits
- [ ] Change PIN updates `staff_pin_hash` with bcrypt
- [ ] Returns `204` on success
- [ ] Errors: `AUTH_INVALID_PIN`, `AUTH_RATE_LIMITED`, `VALIDATION_ERROR`
- [ ] Never returns `staff_pin_hash`

## Test requirements
- [ ] Backend: `tests/test_auth.py::test_login_success`
- [ ] Backend: `tests/test_auth.py::test_login_invalid_pin`
- [ ] Backend: `tests/test_auth.py::test_login_rate_limited`
- [ ] Backend: `tests/test_auth.py::test_change_pin_success`
- [ ] Backend: `tests/test_auth.py::test_change_pin_invalid_current`
- [ ] Backend: `tests/test_auth.py::test_change_pin_mismatch`
- [ ] Backend: `tests/test_auth.py::test_change_pin_same_as_current`

## Implementation notes
- `passlib[bcrypt]` for hashing
- `python-jose` for JWT
- `slowapi` for rate limit
- JWT expiry from `JWT_EXPIRE_HOURS`

## Dependencies
- Blocked by: B-02, B-03, B-04
- Blocks: B-14, I-01

## Out of scope
- Refresh tokens
- Logout endpoint
- Multi-user accounts

## Constraints
- Files: `backend/app/routers/auth.py`
- Do not add endpoints not in `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-06 Public endpoints
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: L
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, feature

## Goal
Implement public endpoints for guests and board.

## Context
- OpenAPI: `getPublicBranch`, `getPublicBoard`, `joinWaitlist`, `getWaitlistStatus`, `cancelWaitlist`
- Specs: `_docs/specs.md#4-core-flows`, `_docs/specs.md#8-queue-number-and-business-date`

## Acceptance criteria
- [ ] `GET /api/v1/public/branches/{branch_id}` returns store info and `is_waitlist_open`
- [ ] `GET /api/v1/public/branches/{branch_id}/board` returns current call, next up, recent calls (max 3), waiting count
- [ ] `POST /api/v1/branches/{branch_id}/waitlist` creates entry:
  - Validates fields
  - Checks duplicate phone among active statuses
  - Generates `queue_number`, `full_queue_number`, `seq`, `business_date`
  - Generates `status_token`
  - Returns `status_url`
- [ ] `GET /api/v1/waitlist/{queue_number}` returns status:
  - With `token` or `phone_last3`
  - Only current `business_date` when no token
  - `waiting_ahead` includes `WAITING` + `CALLED`
  - `estimated_wait_minutes` = `waiting_ahead × avg_seat_minutes`
  - `remaining_seconds` for `CALLED`
  - Applies lazy no-show
- [ ] `POST /api/v1/waitlist/{queue_number}/cancel` cancels with token or `phone_last3`
- [ ] Rate limit join and lookup: 10/minute per IP
- [ ] Rate limit public branch and board: 30/minute per IP
- [ ] Board never returns names or phones
- [ ] Errors: `WAITLIST_DUPLICATE_PHONE`, `WAITLIST_CLOSED`, `WAITLIST_NOT_FOUND`, `BRANCH_NOT_FOUND`, `RATE_LIMITED`, `VALIDATION_ERROR`

## Test requirements
- [ ] Backend: `tests/test_public_waitlist.py::test_join_waitlist_success`
- [ ] Backend: `tests/test_public_waitlist.py::test_join_waitlist_duplicate_phone`
- [ ] Backend: `tests/test_public_waitlist.py::test_join_waitlist_closed`
- [ ] Backend: `tests/test_public_waitlist.py::test_join_waitlist_invalid_phone`
- [ ] Backend: `tests/test_public_waitlist.py::test_join_waitlist_party_size_out_of_range`
- [ ] Backend: `tests/test_public_waitlist.py::test_join_waitlist_note_too_long`
- [ ] Backend: `tests/test_public_waitlist.py::test_get_status_with_token`
- [ ] Backend: `tests/test_public_waitlist.py::test_get_status_with_phone_last3`
- [ ] Backend: `tests/test_public_waitlist.py::test_get_status_wrong_last3`
- [ ] Backend: `tests/test_public_waitlist.py::test_get_status_not_found`
- [ ] Backend: `tests/test_public_waitlist.py::test_cancel_waitlist_by_guest`
- [ ] Backend: `tests/test_public_waitlist.py::test_cancel_called_requires_confirmation`
- [ ] Backend: `tests/test_public_board.py::test_get_public_branch_success`
- [ ] Backend: `tests/test_public_board.py::test_get_public_branch_not_found`
- [ ] Backend: `tests/test_public_board.py::test_get_board_success`
- [ ] Backend: `tests/test_public_board.py::test_get_board_empty`

## Implementation notes
- `status_token` = `secrets.token_urlsafe(32)`
- Queue number uses `business_date` + `seq`
- Lazy no-show applied on status read
- `phone_last3` verified against stored phone

## Dependencies
- Blocked by: B-02, B-03, B-04
- Blocks: B-07, B-14, I-01

## Out of scope
- External notifications
- Multi-branch

## Constraints
- Files: `backend/app/routers/public.py`, `backend/app/services/waitlist.py`
- Do not add endpoints not in `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-07 Staff waitlist endpoints
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: L
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, feature

## Goal
Implement staff waitlist endpoints.

## Context
- OpenAPI: `listWaitlist`, `callWaitlist`, `seatWaitlist`, `noShowWaitlist`, `restoreWaitlist`, `revertWaitlist`, `cancelWaitlistByStaff`, `editWaitlist`, `reorderWaitlist`
- Specs: `_docs/specs.md#5-state-machine`

## Acceptance criteria
- [ ] `GET /api/v1/staff/waitlist` with `status`, `search`, `party_size`, `limit`, `offset`
  - Default `status=ACTIVE` returns `WAITING` + `CALLED` + `SEATED`
  - `CLOSED` returns `NO_SHOW` + `CANCELLED` + `DONE`
  - `ALL` returns all
  - Sorted by `sort_order` asc, `created_at` asc
  - `search` matches name or phone last 3
  - Applies lazy no-show before returning
- [ ] `POST /api/v1/staff/waitlist/{id}/call` sets `CALLED`, stores `called_at`, `hold_minutes_snapshot`
- [ ] `POST /api/v1/staff/waitlist/{id}/seat` sets `SEATED`, sets `table_id`, sets table `OCCUPIED` in one transaction
- [ ] `POST /api/v1/staff/waitlist/{id}/no-show` sets `NO_SHOW`, sets `closed_at`, releases table if any
- [ ] `POST /api/v1/staff/waitlist/{id}/restore` sets `WAITING`, clears `called_at`, `closed_at`, `hold_minutes_snapshot`, returns to original `sort_order`
- [ ] `POST /api/v1/staff/waitlist/{id}/revert` sets `WAITING`, clears `called_at`, `hold_minutes_snapshot`
- [ ] `POST /api/v1/staff/waitlist/{id}/cancel` sets `CANCELLED`, sets `cancelled_reason`, sets `closed_at`, releases table
- [ ] `POST /api/v1/staff/waitlist/{id}/edit` updates `party_size`, `note`; only `WAITING` or `CALLED`
- [ ] `POST /api/v1/staff/waitlist/reorder` updates `sort_order` for all `WAITING` + `CALLED`; `ordered_ids` must match exactly
- [ ] Phone masked in response (`0900-***-001`)
- [ ] Errors: `WAITLIST_INVALID_STATUS`, `WAITLIST_NOT_FOUND`, `TABLE_NOT_AVAILABLE`, `TABLE_NOT_FOUND`, `VALIDATION_ERROR`

## Test requirements
- [ ] Backend: `tests/test_staff_waitlist.py::test_list_waitlist_active`
- [ ] Backend: `tests/test_staff_waitlist.py::test_list_waitlist_closed`
- [ ] Backend: `tests/test_staff_waitlist.py::test_list_waitlist_all`
- [ ] Backend: `tests/test_staff_waitlist.py::test_list_waitlist_search_name`
- [ ] Backend: `tests/test_staff_waitlist.py::test_list_waitlist_search_phone_last3`
- [ ] Backend: `tests/test_staff_waitlist.py::test_call_waitlist_success`
- [ ] Backend: `tests/test_staff_waitlist.py::test_call_waitlist_invalid_status`
- [ ] Backend: `tests/test_staff_waitlist.py::test_seat_waitlist_success`
- [ ] Backend: `tests/test_staff_waitlist.py::test_seat_waitlist_table_not_available`
- [ ] Backend: `tests/test_staff_waitlist.py::test_seat_waitlist_table_not_found`
- [ ] Backend: `tests/test_staff_waitlist.py::test_no_show_waitlist_success`
- [ ] Backend: `tests/test_staff_waitlist.py::test_no_show_waitlist_invalid_status`
- [ ] Backend: `tests/test_staff_waitlist.py::test_restore_waitlist_success`
- [ ] Backend: `tests/test_staff_waitlist.py::test_restore_waitlist_invalid_status`
- [ ] Backend: `tests/test_staff_waitlist.py::test_revert_waitlist_success`
- [ ] Backend: `tests/test_staff_waitlist.py::test_revert_waitlist_invalid_status`
- [ ] Backend: `tests/test_staff_waitlist.py::test_cancel_waitlist_by_staff`
- [ ] Backend: `tests/test_staff_waitlist.py::test_edit_waitlist_party_size`
- [ ] Backend: `tests/test_staff_waitlist.py::test_edit_waitlist_invalid_status`
- [ ] Backend: `tests/test_staff_waitlist.py::test_reorder_waitlist_success`
- [ ] Backend: `tests/test_staff_waitlist.py::test_reorder_waitlist_missing_ids`
- [ ] Backend: `tests/test_staff_waitlist.py::test_reorder_waitlist_extra_ids`

## Implementation notes
- All state changes in transactions
- `GET` triggers lazy no-show
- `remaining_seconds` only for `CALLED`
- Seat validates table `AVAILABLE` in same transaction
- Cancel releases table if `SEATED`

## Dependencies
- Blocked by: B-02, B-03, B-04, B-06
- Blocks: B-09, B-14, I-01

## Out of scope
- Change table
- Drag-and-drop

## Constraints
- Files: `backend/app/routers/staff.py`, `backend/app/services/waitlist.py`
- Do not add endpoints not in `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-08 Staff tables endpoints
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, feature

## Goal
Implement staff table endpoints.

## Context
- OpenAPI: `listTables`, `updateTableStatus`, `releaseTable`
- Specs: `_docs/specs.md#9-table-management`

## Acceptance criteria
- [ ] `GET /api/v1/staff/tables` returns active tables
  - `current_waitlist` only for `OCCUPIED`, with `queue_number`, `party_size`, `seated_at`, `elapsed_minutes`
  - Sorted by `sort_order`, `label`
- [ ] `PATCH /api/v1/staff/tables/{id}` accepts `AVAILABLE` or `CLEANING` only
- [ ] `PATCH` rejects `OCCUPIED` with `VALIDATION_ERROR`
- [ ] `POST /api/v1/staff/tables/{id}/release` releases `OCCUPIED` → `AVAILABLE`, sets corresponding entry `DONE`, sets `closed_at` in one transaction
- [ ] Release rejects non-`OCCUPIED` with `TABLE_NOT_AVAILABLE`
- [ ] Errors: `TABLE_NOT_FOUND`, `TABLE_NOT_AVAILABLE`, `VALIDATION_ERROR`

## Test requirements
- [ ] Backend: `tests/test_staff_tables.py::test_list_tables_active`
- [ ] Backend: `tests/test_staff_tables.py::test_list_tables_includes_current_waitlist`
- [ ] Backend: `tests/test_staff_tables.py::test_update_table_status_available_to_cleaning`
- [ ] Backend: `tests/test_staff_tables.py::test_update_table_status_cleaning_to_available`
- [ ] Backend: `tests/test_staff_tables.py::test_update_table_status_occupied_rejected`
- [ ] Backend: `tests/test_staff_tables.py::test_release_table_success`
- [ ] Backend: `tests/test_staff_tables.py::test_release_table_not_occupied`

## Implementation notes
- `elapsed_minutes` = minutes since `seated_at`
- Release transaction updates table + entry
- Inactive tables excluded

## Dependencies
- Blocked by: B-02, B-03, B-04
- Blocks: B-09, B-14, I-01

## Out of scope
- Table merging
- Drag-and-drop
- Seating from tables page

## Constraints
- Files: `backend/app/routers/staff.py`, `backend/app/services/tables.py`
- Do not add endpoints not in `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-09 Staff dashboard endpoint
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: S
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, feature

## Goal
Implement `GET /api/v1/staff/dashboard`.

## Context
- OpenAPI: `getDashboard`
- Specs: `_docs/specs.md#12-api-summary`

## Acceptance criteria
- [ ] Returns `waiting_count`, `called_count`, `seated_count`
- [ ] Returns `available_table_count`, `occupied_table_count`, `cleaning_table_count`
- [ ] Returns `no_show_today`, `cancelled_today`, `seated_today` (current `business_date`)
- [ ] Returns `avg_wait_minutes_today` (null if no data)
- [ ] Applies lazy no-show first
- [ ] Only active tables counted

## Test requirements
- [ ] Backend: `tests/test_staff_dashboard.py::test_dashboard_counts`
- [ ] Backend: `tests/test_staff_dashboard.py::test_dashboard_avg_wait_null_when_no_data`

## Implementation notes
- `seated_today` counts `SEATED` + `DONE`
- `avg_wait_minutes_today` = average of `seated_at - created_at`
- No caching

## Dependencies
- Blocked by: B-02, B-03, B-04, B-07, B-08
- Blocks: B-14, I-01

## Out of scope
- Historical reports
- CSV export

## Constraints
- Files: `backend/app/routers/staff.py`, `backend/app/services/waitlist.py`
- Do not add endpoints not in `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-10 Admin settings endpoints
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, feature

## Goal
Implement `GET /api/v1/admin/settings` and `PATCH /api/v1/admin/settings`.

## Context
- OpenAPI: `getSettings`, `updateSettings`
- Specs: `_docs/specs.md#7-business-rules`

## Acceptance criteria
- [ ] `GET` returns store info, waitlist settings, notification templates, `has_pin`
- [ ] `GET` never returns `staff_pin_hash`
- [ ] `PATCH` updates allowed fields
- [ ] `PATCH` validates ranges:
  - `hold_minutes` 5–15
  - `avg_seat_minutes` 5–60
  - `queue_prefix` `^[A-Z]{1,3}$`
  - `open_time`, `close_time` `HH:MM`
- [ ] `PATCH` validates `notification_templates` has all three keys
- [ ] `PATCH` updates `updated_at`
- [ ] Errors: `VALIDATION_ERROR`, `SETTINGS_NOT_FOUND`

## Test requirements
- [ ] Backend: `tests/test_admin_settings.py::test_get_settings_success`
- [ ] Backend: `tests/test_admin_settings.py::test_update_settings_success`
- [ ] Backend: `tests/test_admin_settings.py::test_update_settings_hold_minutes_out_of_range`
- [ ] Backend: `tests/test_admin_settings.py::test_update_settings_queue_prefix_invalid`
- [ ] Backend: `tests/test_admin_settings.py::test_update_settings_notification_templates`

## Implementation notes
- `has_pin` = `staff_pin_hash is not None`
- Notification templates stored as JSON
- `queue_prefix` change only affects future entries

## Dependencies
- Blocked by: B-02, B-03, B-04
- Blocks: B-14, I-01

## Out of scope
- PIN change (in auth)

## Constraints
- Files: `backend/app/routers/admin.py`, `backend/app/services/settings.py`
- Do not add endpoints not in `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-11 Admin tables endpoints
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, feature

## Goal
Implement admin table CRUD.

## Context
- OpenAPI: `listAdminTables`, `createTable`, `updateTable`, `deleteTable`
- Specs: `_docs/specs.md#9-table-management`

## Acceptance criteria
- [ ] `GET /api/v1/admin/tables` with `include_inactive`
- [ ] `POST /api/v1/admin/tables` creates table, unique label per branch
- [ ] `PATCH /api/v1/admin/tables/{id}` updates table, unique label per branch
- [ ] `DELETE /api/v1/admin/tables/{id}` soft-deletes, rejects if `OCCUPIED` with `CONFLICT`
- [ ] `label` 1–10 chars, `capacity` 1–20, `section` 0–50 chars
- [ ] `sort_order` optional, integer
- [ ] Errors: `CONFLICT`, `TABLE_NOT_FOUND`, `VALIDATION_ERROR`

## Test requirements
- [ ] Backend: `tests/test_admin_tables.py::test_create_table_success`
- [ ] Backend: `tests/test_admin_tables.py::test_create_table_duplicate_label`
- [ ] Backend: `tests/test_admin_tables.py::test_update_table_success`
- [ ] Backend: `tests/test_admin_tables.py::test_update_table_duplicate_label`
- [ ] Backend: `tests/test_admin_tables.py::test_delete_table_soft`
- [ ] Backend: `tests/test_admin_tables.py::test_delete_table_occupied_conflict`
- [ ] Backend: `tests/test_admin_tables.py::test_list_admin_tables_include_inactive`

## Implementation notes
- Soft delete via `is_active=false`
- Inactive tables excluded from staff tables and suggestions
- Inactive tables shown in admin list with `(deleted)`

## Dependencies
- Blocked by: B-02, B-03, B-04
- Blocks: B-14, I-01

## Out of scope
- Hard delete

## Constraints
- Files: `backend/app/routers/admin.py`, `backend/app/services/tables.py`
- Do not add endpoints not in `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-12 Admin reset endpoint
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: S
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, feature

## Goal
Implement `POST /api/v1/admin/reset`.

## Context
- OpenAPI: `resetData`
- Specs: `_docs/specs.md#4-core-flows`

## Acceptance criteria
- [ ] Only allowed when `ENV=development`
- [ ] Requires body `{ "confirm": "RESET" }`
- [ ] Returns `204` on success
- [ ] Returns `403` in non-development
- [ ] Returns `VALIDATION_ERROR` if confirm wrong
- [ ] Runs seed reset logic

## Test requirements
- [ ] Backend: `tests/test_admin_reset.py::test_reset_success_dev`
- [ ] Backend: `tests/test_admin_reset.py::test_reset_forbidden_production`
- [ ] Backend: `tests/test_admin_reset.py::test_reset_wrong_confirm`

## Implementation notes
- Reuse `app.seed --reset` logic
- Do not allow in `test` env if `ENV=test` (only `development`)

## Dependencies
- Blocked by: B-02, B-03, B-04, B-13
- Blocks: B-14, I-01

## Out of scope
- Production data reset

## Constraints
- Files: `backend/app/routers/admin.py`
- Do not add endpoints not in `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-13 Seed script
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: feature
- **Area**: backend
- **Size**: M
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, feature

## Goal
Create `python -m app.seed` with `--reset`.

## Context
- Specs: `_docs/specs.md#19-seed-data`

## Acceptance criteria
- [ ] Creates Restaurant `Sunny Bistro`
- [ ] Creates Branch `Taipei Xinyi` with address, phone, hours, timezone, cutoff
- [ ] Creates Settings with `hold_minutes=10`, `avg_seat_minutes=15`, `queue_prefix=A`, `is_waitlist_open=true`, `sound_enabled_default=true`
- [ ] Creates 10 tables: `A1–A4` (2 pax), `B1–B4` (4 pax), `C1–C2` (6 pax)
- [ ] Creates 5 `WAITING` with different party sizes and notes
- [ ] Creates 1 `CALLED` with `called_at` 3 minutes ago
- [ ] Creates 1 `SEATED` on `B1`
- [ ] Creates 1 `NO_SHOW`
- [ ] Creates 1 `CANCELLED`
- [ ] All `business_date = today`
- [ ] Phones `0900-000-001` to `0900-000-009`
- [ ] Without `--reset`: skips existing data
- [ ] With `--reset`: clears and re-seeds
- [ ] Idempotent without `--reset`

## Test requirements
- [ ] Backend: `tests/test_seed.py::test_seed_reset_creates_expected_data`
- [ ] Backend: `tests/test_seed.py::test_seed_without_reset_skips_existing`
- [ ] Manual: `uv run python -m app.seed --reset`

## Implementation notes
- `--reset` truncates tables first
- Uses SQLAlchemy session
- Fixed phones and names
- `created_at` spread over time for realistic waiting durations

## Dependencies
- Blocked by: B-02
- Blocks: B-12, B-14, I-02

## Out of scope
- Frontend seed

## Constraints
- Files: `backend/app/seed.py`
- Do not add data not in `_docs/specs.md#19-seed-data`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
B-14 Backend tests
markdown
## Metadata
- **Phase**: phase-2-backend
- **Type**: test
- **Area**: backend
- **Size**: L
- **Milestone**: Phase 2 — Backend + Mock DB
- **Labels**: groomed, phase-2-backend, backend, test

## Goal
Ensure all backend tests pass with coverage.

## Context
- Testing: `_docs/testing.md#2-backend-tests`

## Acceptance criteria
- [ ] `tests/conftest.py` with `db`, `client`, `fixed_now`, `staff_token`, `auth_headers`
- [ ] `tests/factories.py` with `make_branch`, `make_table`, `make_waitlist_entry`, `make_settings`, `make_staff_token`
- [ ] Test files:
  - `test_health.py`
  - `test_auth.py`
  - `test_public_waitlist.py`
  - `test_public_board.py`
  - `test_staff_waitlist.py`
  - `test_staff_tables.py`
  - `test_staff_dashboard.py`
  - `test_admin_settings.py`
  - `test_admin_tables.py`
  - `test_admin_reset.py`
  - `test_state_machine.py`
  - `test_seed.py`
  - `test_models.py`
  - `test_schemas.py`
  - `test_errors.py`
- [ ] `uv run pytest` passes
- [ ] Coverage ≥ 80% on services and routers
- [ ] Boundary tests for `business_date`
- [ ] Lazy no-show tests with fixed time
- [ ] State machine transition tests

## Test requirements
- [ ] All tests pass

## Implementation notes
- in-memory SQLite
- `freezegun` for time
- `TestClient` with `get_db` override
- Factories mirror seed data

## Dependencies
- Blocked by: B-05, B-06, B-07, B-08, B-09, B-10, B-11, B-12, B-13
- Blocks: I-01

## Out of scope
- E2E
- Concurrency tests

## Constraints
- Files: `backend/tests/`
- Do not add tests for features not in `_docs/specs.md`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue

I-01 Switch frontend to real API
markdown
## Metadata
- **Phase**: phase-3-integration
- **Type**: chore
- **Area**: frontend, backend
- **Size**: M
- **Milestone**: Phase 3 — Integration
- **Labels**: groomed, phase-3-integration, frontend, backend, chore

## Goal
Turn off frontend mock, point frontend to real backend, verify all endpoints work end-to-end.

## Context
- OpenAPI: `_docs/openapi.yaml`
- Agent guide: `AGENTS.md#8-frontend-guidelines`
- Deployment: `_docs/deployment.md#1-local-development`

## Acceptance criteria
- [ ] `frontend/.env` sets `VITE_USE_MOCK=false`
- [ ] Vite proxy `/api` → `http://localhost:8000` works
- [ ] `VITE_API_BASE_URL=/api/v1`
- [ ] `VITE_BRANCH_ID=1`
- [ ] `VITE_PUBLIC_BASE_URL` empty (uses `window.location.origin`)
- [ ] `frontend/src/api/mock/` is bypassed when `VITE_USE_MOCK=false`
- [ ] All frontend pages load real data
- [ ] No CORS errors in console
- [ ] Error codes display correct English messages
- [ ] 401 redirects to `/staff/login`
- [ ] `npm run test` still passes
- [ ] `npm run build` succeeds

## Test requirements
- [ ] Manual: open `/join?branch=1`, join, see status
- [ ] Manual: open `/staff/login`, log in with PIN `1234`
- [ ] Manual: call, seat, release, close day
- [ ] Manual: open `/board/1`, see current call
- [ ] Manual: open `/admin/settings`, change `hold_minutes`
- [ ] Manual: confirm error messages for duplicate phone and invalid PIN

## Implementation notes
- Answer the question: **Which URL does the frontend use to talk to the backend?**
  - Development: `/api/v1` via Vite proxy → `http://localhost:8000`
  - Production: `VITE_API_BASE_URL` set to backend URL
- Do not change API shapes; `_docs/openapi.yaml` is the contract
- Do not change backend logic in this issue
- If a bug is found, open a new bug issue; do not fix here

## Dependencies
- Blocked by: B-14, F-15
- Blocks: I-02

## Out of scope
- Backend changes
- New features
- Production deployment

## Constraints
- Files: `frontend/.env`, `frontend/vite.config.ts`, `frontend/src/api/client.ts`
- Do not edit `_docs/specs.md`
- Do not edit `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `npm run test` passes
- [ ] `npm run build` passes
- [ ] PR references this issue
I-02 Verify end-to-end flow
markdown
## Metadata
- **Phase**: phase-3-integration
- **Type**: test
- **Area**: frontend, backend
- **Size**: M
- **Milestone**: Phase 3 — Integration
- **Labels**: groomed, phase-3-integration, frontend, backend, test

## Goal
Verify full flow works end-to-end using `_docs/demo.md`.

## Context
- Demo: `_docs/demo.md`
- API examples: `_docs/api-examples.md`
- Seed: `_docs/specs.md#19-seed-data`

## Acceptance criteria
- [ ] Run `make seed`
- [ ] Run `make dev`
- [ ] Step 1: Join waitlist → `/status/A006?token=...`
- [ ] Step 2: Staff login → `/staff/waitlist`
- [ ] Step 3: Call `A006` → guest page turns orange, countdown starts
- [ ] Step 4: Seat `A006` on `A1` → table map shows `OCCUPIED`
- [ ] Step 5: No-show and restore `A001`
- [ ] Step 6: Open `/board/1` → shows current call, QR code
- [ ] Step 7: Change `hold_minutes` in settings → new call uses new value
- [ ] Step 8: Release table → entry `DONE`, table `AVAILABLE`
- [ ] Step 9: Close day → all active closed
- [ ] Step 10: Reset data (dev only)
- [ ] `_docs/demo.md` checklist all checked
- [ ] No console errors in browser
- [ ] No backend errors in terminal
- [ ] Error states verified manually

## Test requirements
- [ ] Manual: follow `_docs/demo.md` step by step
- [ ] Optional: ask coding agent to use a browser to verify
- [ ] Capture screenshots for PR

## Implementation notes
- If any step fails, open a new bug issue; do not fix in this issue
- Do not add features
- Do not change `_docs/demo.md`

## Dependencies
- Blocked by: I-01
- Blocks: D-01

## Out of scope
- Automated E2E tests
- Backend changes
- New features

## Constraints
- Do not modify `_docs/specs.md`
- Do not modify `_docs/openapi.yaml`
- Do not commit screenshots into repo

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Demo checklist all checked
- [ ] PR references this issue
D-01 Swap mock store for real SQLAlchemy DB
markdown
## Metadata
- **Phase**: phase-4-database
- **Type**: chore
- **Area**: database, backend
- **Size**: M
- **Milestone**: Phase 4 — Database
- **Labels**: groomed, phase-4-database, database, backend, chore

## Goal
Confirm backend uses SQLAlchemy + SQLite as the real DB (not an in-memory mock), and that the app is database-agnostic so it can swap to PostgreSQL later.

## Context
- Specs: `_docs/specs.md#6-data-model`, `_docs/specs.md#14-concurrency`
- Deployment: `_docs/deployment.md#3-database`
- Agent guide: `AGENTS.md#7-backend-guidelines`

## Acceptance criteria
- [ ] Backend uses SQLAlchemy 2.0 for all persistence
- [ ] `DATABASE_URL` drives the connection string
- [ ] Default dev: `sqlite:///./dev.db`
- [ ] Test: `sqlite:///:memory:`
- [ ] No raw SQL in routers
- [ ] All writes go through service layer
- [ ] Restart backend: data persists
- [ ] Changing `DATABASE_URL` to PostgreSQL requires no code change
- [ ] `Base.metadata.create_all` runs on startup
- [ ] No Alembic in v1
- [ ] `backend/dev.db` is gitignored
- [ ] `engine.dispose()` called on shutdown
- [ ] SQLite uses `check_same_thread=False`

## Test requirements
- [ ] Manual: restart backend, data still there
- [ ] Manual: delete `dev.db`, restart, default Restaurant/Branch/Settings recreated
- [ ] Manual: `DATABASE_URL=postgresql+psycopg://...` starts without import errors (no actual DB needed)
- [ ] Backend: `tests/test_models.py::test_persist_across_sessions`

## Implementation notes
- Keep app database-agnostic
- Use SQLAlchemy for all DB access
- Do not import SQLite-specific code outside `database.py`
- Write the answer to: **Which command do you use for running tests?**
  - `cd backend && uv run pytest`
  - Or `make test-backend`
- Ask agent for recommendations if unsure

## Dependencies
- Blocked by: I-02
- Blocks: D-02

## Out of scope
- Alembic migrations
- Production PostgreSQL setup
- Data migration from SQLite to PostgreSQL

## Constraints
- Files: `backend/app/database.py`, `backend/app/services/`, `backend/app/models.py`
- Do not change API shapes
- Do not edit `_docs/specs.md`
- Do not edit `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] `make dev` runs
- [ ] PR references this issue
D-02 Add more tests
markdown
## Metadata
- **Phase**: phase-4-database
- **Type**: test
- **Area**: database, backend
- **Size**: M
- **Milestone**: Phase 4 — Database
- **Labels**: groomed, phase-4-database, database, backend, test

## Goal
Add more tests to cover database-specific behavior, transactions, and edge cases.

## Context
- Testing: `_docs/testing.md#2-backend-tests`
- Specs: `_docs/specs.md#14-concurrency`

## Acceptance criteria
- [ ] Tests cover unique constraints at DB level
- [ ] Tests cover transaction rollback on error
- [ ] Tests cover `business_date` boundary with fixed time:
  - `2026-09-10 03:59` Taipei → `2026-09-09`
  - `2026-09-10 04:00` Taipei → `2026-09-10`
  - `2026-09-11 01:00` Taipei → `2026-09-10`
- [ ] Tests cover lazy no-show with fixed time
- [ ] Tests cover close day transaction
- [ ] Tests cover release table transaction
- [ ] Tests cover seat transaction (entry + table atomic)
- [ ] Tests cover reorder transaction
- [ ] Tests cover duplicate phone race condition (via transaction retry)
- [ ] Tests cover queue number conflict retry
- [ ] `uv run pytest` passes
- [ ] Coverage ≥ 80% on services and routers

## Test requirements
- [ ] Add tests to `tests/test_state_machine.py`
- [ ] Add tests to `tests/test_models.py`
- [ ] Add tests to `tests/test_staff_waitlist.py`
- [ ] Add tests to `tests/test_staff_tables.py`
- [ ] Add tests to `tests/test_public_waitlist.py`

## Implementation notes
- Use in-memory SQLite for tests
- Use `freezegun` for time
- Ask agent for recommendations if unsure
- Do not add tests for features not in `_docs/specs.md`

## Dependencies
- Blocked by: D-01
- Blocks: D-03

## Out of scope
- Load tests
- Concurrency tests with real threads
- E2E tests
- Frontend tests

## Constraints
- Files: `backend/tests/`
- Do not edit `_docs/specs.md`
- Do not add features

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `uv run pytest` passes
- [ ] PR references this issue
D-03 Verify all tests pass
markdown
## Metadata
- **Phase**: phase-4-database
- **Type**: test
- **Area**: database, backend, frontend
- **Size**: S
- **Milestone**: Phase 4 — Database
- **Labels**: groomed, phase-4-database, database, backend, frontend, test

## Goal
Final verification that everything passes and the app still works after the DB swap.

## Context
- Testing: `_docs/testing.md`
- Demo: `_docs/demo.md`
- Deployment: `_docs/deployment.md`

## Acceptance criteria
- [ ] `cd backend && uv run pytest` passes
- [ ] `cd frontend && npm run test` passes
- [ ] `make test` passes
- [ ] `make seed` runs
- [ ] `make dev` runs
- [ ] Manual demo from `_docs/demo.md` still works
- [ ] No lint errors:
  - `cd frontend && npm run lint`
  - `cd backend && uv run ruff check .`
- [ ] All Phase 4 issues closed
- [ ] `backend/dev.db` persists data across restart
- [ ] No regression in any endpoint
- [ ] Error codes still correct
- [ ] `X-Request-ID` header present
- [ ] Security headers present

## Test requirements
- [ ] Run all commands above
- [ ] Follow `_docs/demo.md` end to end
- [ ] Capture final screenshots

## Implementation notes
- If anything fails, open a new bug issue; do not fix in this issue
- Do not add features
- Do not modify `_docs/specs.md`

## Dependencies
- Blocked by: D-02
- Blocks: None

## Out of scope
- Production deployment
- New features
- Refactoring

## Constraints
- Do not add features
- Do not edit `_docs/specs.md`
- Do not edit `_docs/openapi.yaml`

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] `make test` passes
- [ ] Demo works
- [ ] PR references this issue
Appendix: Phase Completion Checklist
Phase 0 completion criteria
□ P0-01 through P0-11 all closed
□ _docs/specs.md, _docs/ui.md, _docs/openapi.yaml, _docs/testing.md, _docs/deployment.md, _docs/api-examples.md, _docs/demo.md, README.md, CONTRIBUTING.md, AGENTS.md, _docs/plan.md all exist
□ openapi.yaml passes lint
Phase 1 completion criteria
□ F-01 through F-15 all closed
□ VITE_USE_MOCK=true drives all major features
□ npm run test passes
□ all pages have empty, loading and error states
Phase 2 completion criteria
□ B-01 through B-14 all closed
□ uv run pytest passes
□ Swagger UI shows every endpoint
□ make seed produces demo data
□ error format is uniform
Phase 3 completion criteria
□ I-01 and I-02 closed
□ VITE_USE_MOCK=false drives all major features
□ every step in _docs/demo.md passes
□ frontend calls the backend via /api/v1
Phase 4 completion criteria
□ D-01, D-02 and D-03 closed
□ make test passes
□ data survives a restart
□ changing DATABASE_URL needs no code change
□ all known limitations are written into _docs/specs.md
