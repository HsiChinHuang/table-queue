# TableQueue — Specifications

Version: 0.1.0
Status: Draft
Last updated: 2026-09-10

---

## 1. Overview

TableQueue is a restaurant waitlist manager.

- Guests join the waitlist via QR code or direct URL.
- Staff manage the queue and tables from a tablet or desktop dashboard.
- Admins configure store info, waitlist rules, tables, PIN, and notification templates.
- Built with FastAPI (Python + uv) and React (Node.js + Vite).
- Single-store MVP, but data model keeps `restaurant_id` and `branch_id` for future expansion.
- All UI text is in English. Formats follow Taiwan localization (phone, timezone).

---

## 2. Goals and Non-Goals

### Goals
- End-to-end waitlist flow: join → waiting → called → seated → done.
- Handle no-show with a configurable hold time and auto-marking.
- Table management with manual status and suggested tables.
- Pretty, consistent UI across guest and staff experiences.
- Simple development with low-capability coding agents.

### Non-Goals (v1)
- Multi-branch UI
- Reports page and CSV export
- Advanced notification templates
- Dark mode
- i18n framework
- Playwright E2E
- Concurrency tests
- Alembic migrations
- Docker
- Production deployment
- Drag-and-drop seating
- Table merging
- Audit log
- Optimistic locking
- Frontend real-time locking
- Print waitlist slip
- Shift handover
- Walk-in direct seating
- Soft delete for waitlist entries
- Status change history
- `Settings.updated_by`
- Multi-tab sync
- Offline mode
- PWA
- Analytics
- Error tracking
- Feature flags
- A/B testing
- Push notifications
- Email / SMS / LINE notifications
- Payment
- Reservation
- Loyalty
- Review
- Multi-language
- Multi-currency
- Multi-tenant
- Role-based access (single shared PIN in v1)
- Queue / background workers
- Cron / scheduled jobs
- Cache layer
- Structured logging
- Log rotation
- DB connection pool tuning
- Frontend bundle size limit
- Query placeholderData / select / initialData / gcTime / networkMode / refetchOnReconnect customization
- Sonner Toaster customization beyond defaults
- Lucide icon list customization
- shadcn/ui component list customization
- Tailwind @layer customization
- Layout background customization
- Status color token customization
- Font size spec customization
- Button min height customization
- Radius / shadow / spacing / max-w / grid / flex / transition / hover / focus / disabled / loading / error / empty spec customization
- a11y spec beyond baseline
- i18n, dark mode, RTL, PWA, offline, analytics, error tracking, feature flag, A/B test, push notification, email/SMS/LINE, payment, reservation, loyalty, review, multi-language, multi-currency, multi-tenant, RBAC, audit log, soft delete, versioning, rate limit persistence, cache, queue, cron

---

## 3. Roles and Permissions

### Guest
- Join waitlist
- View own status
- Cancel own waitlist entry

### Staff
- All guest actions
- List waitlist
- Call, seat, no-show, restore, revert, cancel
- Edit party size and note
- Reorder waitlist
- View and update table status
- View dashboard

### Admin
- All staff actions
- Read and update settings
- Create, update, soft-delete tables
- Change staff PIN
- Reset data (development only)

### Auth Model
- Guests: no account. Use `status_token` or `queue_number` + `phone_last3`.
- Staff/Admin: single shared PIN. Login returns JWT.
- JWT payload: `sub="staff"`, `role="staff"`, `iat`, `exp`.
- JWT algorithm: HS256. Secret from `JWT_SECRET`.
- JWT expiry: `JWT_EXPIRE_HOURS`, default 12.

---

## 4. Core Flows

### 4.1 Guest joins waitlist
1. Guest opens `/join?branch=1`.
2. Frontend calls `GET /api/v1/public/branches/1`.
3. If `is_waitlist_open=false`, show closed message.
4. Guest fills name, phone, party size, optional note.
5. Frontend calls `POST /api/v1/branches/1/waitlist`.
6. Backend validates, checks duplicate phone, generates queue number.
7. Backend returns `queue_number`, `full_queue_number`, `status_token`, `status_url`.
8. Frontend navigates to `/status/A001?token=xxx`.

### 4.2 Staff calls next guest
1. Staff opens `/staff/waitlist`.
2. Frontend calls `GET /api/v1/staff/waitlist?status=ACTIVE`.
3. Staff clicks `Call` on a `WAITING` entry.
4. Frontend calls `POST /api/v1/staff/waitlist/{id}/call`.
5. Backend sets status to `CALLED`, stores `called_at`, stores `hold_minutes_snapshot`.
6. Backend returns updated entry with `remaining_seconds`.
7. Guest status page shows `CALLED`, countdown, orange color, vibration, sound.

### 4.3 Guest is seated
1. Staff clicks `Seat` on a `CALLED` or `WAITING` entry.
2. Dialog shows available tables sorted by capacity match.
3. Staff selects a table.
4. Frontend calls `POST /api/v1/staff/waitlist/{id}/seat` with `table_id`.
5. Backend validates table is `AVAILABLE`, sets status to `SEATED`, sets `seated_at`, sets `table_id`.
6. Backend sets table status to `OCCUPIED`.
7. Guest status page shows `SEATED` and "You're seated. Enjoy your meal!".

### 4.4 No-show
1. Staff clicks `No-show` on a `CALLED` entry, or hold time expires.
2. Backend sets status to `NO_SHOW`, sets `closed_at`.
3. Backend releases table if any.
4. Guest status page shows `No-show`.
5. Staff can `Restore` to `WAITING`.

### 4.5 Restore
1. Staff clicks `Restore` on a `NO_SHOW` entry.
2. Backend sets status to `WAITING`, clears `called_at`, `closed_at`, `hold_minutes_snapshot`.
3. Entry returns to original `sort_order`.
4. If original `sort_order` is taken, reorder.

### 4.6 Revert call
1. Staff clicks `Revert` on a `CALLED` entry.
2. Backend sets status to `WAITING`, clears `called_at`, `hold_minutes_snapshot`.
3. Entry returns to original `sort_order`.

### 4.7 Cancel
1. Guest clicks `Cancel` on `/status`.
2. If `WAITING`, cancel directly.
3. If `CALLED`, show confirmation dialog.
4. Backend sets status to `CANCELLED`, sets `cancelled_reason`, sets `closed_at`.
5. Backend releases table if any.
6. Guest status page shows `Cancelled` and `Join Again`.

### 4.8 Release table
1. Staff clicks `Release Table` on an `OCCUPIED` table.
2. Confirmation dialog.
3. Backend sets table status to `AVAILABLE`.
4. Backend sets corresponding `SEATED` entry to `DONE`, sets `closed_at`.

### 4.9 Close day
1. Staff clicks `Close Day` on the waitlist page.
2. Confirmation dialog.
3. Backend sets all `WAITING` and `CALLED` to `CANCELLED` with `cancelled_reason=CLOSED_DAY`.
4. Backend sets all `SEATED` to `DONE`.
5. Backend sets all `OCCUPIED` tables to `CLEANING`.

### 4.10 Lazy no-show
- Any API that reads a `CALLED` entry checks `called_at + hold_minutes_snapshot < now`.
- If expired, backend sets status to `NO_SHOW`, sets `closed_at`.
- This happens on `GET /staff/waitlist`, `GET /waitlist/{queue_number}`, `GET /staff/dashboard`.

---

## 5. State Machine

### Waitlist states
- `WAITING`
- `CALLED`
- `SEATED`
- `DONE`
- `NO_SHOW`
- `CANCELLED`

### Table states
- `AVAILABLE`
- `OCCUPIED`
- `CLEANING`

### Allowed transitions

| From | Action | To | Actor |
|---|---|---|---|
| `WAITING` | Call | `CALLED` | Staff |
| `WAITING` | Seat | `SEATED` | Staff |
| `WAITING` | Cancel | `CANCELLED` | Guest / Staff |
| `WAITING` | Edit | `WAITING` | Staff |
| `WAITING` | Reorder | `WAITING` | Staff |
| `CALLED` | Seat | `SEATED` | Staff |
| `CALLED` | No-show (manual or timeout) | `NO_SHOW` | Staff / System |
| `CALLED` | Revert | `WAITING` | Staff |
| `CALLED` | Cancel | `CANCELLED` | Guest (confirm) / Staff |
| `CALLED` | Edit | `CALLED` | Staff |
| `SEATED` | Done (release table) | `DONE` | Staff |
| `SEATED` | Cancel | `CANCELLED` | Staff |
| `NO_SHOW` | Restore | `WAITING` | Staff |
| `CANCELLED` | — | — | Not recoverable |
| `DONE` | — | — | Not recoverable |

### Table transitions

| From | Action | To | Actor |
|---|---|---|---|
| `AVAILABLE` | Mark cleaning | `CLEANING` | Staff |
| `CLEANING` | Mark available | `AVAILABLE` | Staff |
| `AVAILABLE` | Seat guest | `OCCUPIED` | Staff |
| `OCCUPIED` | Release | `AVAILABLE` | Staff |

- `OCCUPIED` cannot be set directly via `PATCH /staff/tables/{id}`.

---

## 6. Data Model

### Restaurant
- `id` integer PK
- `name` string
- `created_at` datetime UTC
- `updated_at` datetime UTC

### Branch
- `id` integer PK
- `restaurant_id` FK → restaurants.id
- `name` string
- `address` string
- `phone` string
- `timezone` string, default `Asia/Taipei`
- `business_day_cutoff_hour` integer, default 4
- `open_time` string `HH:MM`
- `close_time` string `HH:MM`
- `created_at` datetime UTC
- `updated_at` datetime UTC

### Table
- `id` UUID PK
- `branch_id` FK → branches.id
- `label` string
- `capacity` integer
- `section` string nullable
- `sort_order` integer
- `status` enum `AVAILABLE` | `OCCUPIED` | `CLEANING`
- `is_active` boolean
- `created_at` datetime UTC
- `updated_at` datetime UTC

Unique: `(branch_id, label)`

### WaitlistEntry
- `id` UUID PK
- `branch_id` FK → branches.id
- `queue_number` string, e.g. `A001`
- `full_queue_number` string, e.g. `A-20260910-001`
- `queue_prefix` string
- `seq` integer
- `business_date` string `YYYY-MM-DD`
- `name` string
- `phone` string, normalized digits
- `party_size` integer
- `note` string nullable
- `status` enum
- `sort_order` integer
- `source` enum `CUSTOMER` | `STAFF`
- `hold_minutes_snapshot` integer nullable
- `cancelled_reason` enum nullable `CUSTOMER` | `STAFF` | `CLOSED_DAY` | `RESET`
- `table_id` UUID nullable FK → tables.id
- `created_at` datetime UTC
- `updated_at` datetime UTC
- `called_at` datetime UTC nullable
- `seated_at` datetime UTC nullable
- `closed_at` datetime UTC nullable

Unique: `(branch_id, business_date, queue_prefix, seq)`

### Settings
- `id` integer PK
- `branch_id` FK → branches.id, unique
- `hold_minutes` integer, default 10
- `avg_seat_minutes` integer, default 15
- `queue_prefix` string, default `A`
- `is_waitlist_open` boolean, default true
- `sound_enabled_default` boolean, default true
- `notification_templates` JSON
- `staff_pin_hash` string nullable
- `created_at` datetime UTC
- `updated_at` datetime UTC

### Notification templates JSON shape
```json
{
  "joined": "You're on the waitlist. Your number is {queue_number}.",
  "called": "It's your turn! Please come to the counter within {hold_minutes} minutes.",
  "no_show": "Your number has been called and marked as no-show."
}
```

7. Business Rules
Phone must be unique among active statuses (WAITING, CALLED, SEATED).

Name: 1–50 chars, trimmed.

Phone: Taiwan mobile 09xx-xxx-xxx or landline 02-xxxx-xxxx.

Party size: 1–20.

Note: 0–200 chars, trimmed.

Hold minutes: 5–15, default 10.

Avg seat minutes: 5–60, default 15.

Queue prefix: 1–3 uppercase letters.

Business day cutoff hour: 4.

CALLED → NO_SHOW after hold_minutes_snapshot minutes.

NO_SHOW can be restored.

CALLED can be reverted.

SEATED can be cancelled by staff.

Table released on cancel, done, or no-show.

Table status: AVAILABLE, OCCUPIED, CLEANING.

OCCUPIED only via seat.

CLEANING manual.

Release table → entry DONE.

queue_prefix change only affects future entries.

hold_minutes change applies to future calls; existing calls use snapshot.

8. Queue Number and Business Date
business_date = (now_in_branch_tz - cutoff_hour).date().

Example: cutoff=4, 2026-09-11 01:00 Taipei → business_date = 2026-09-10.

seq = max seq for same (branch_id, business_date, queue_prefix) + 1.

queue_number display: A001.

full_queue_number unique: A-20260910-001.

queue_number resets daily.

queue_number is not unique across days.

Guest lookup without token only searches current business_date.

9. Table Management
Static table list maintained in Settings.

Table fields: label, capacity, section, sort_order, is_active.

Table status: AVAILABLE, OCCUPIED, CLEANING.

Staff can toggle AVAILABLE ↔ CLEANING.

OCCUPIED only via seat.

Staff can release OCCUPIED → AVAILABLE.

Suggested tables: filter AVAILABLE, sort by capacity match, then sort_order.

No table merging in v1.

Soft delete via is_active=false.

Inactive tables excluded from staff tables and suggestions.

Inactive tables shown in admin list with (deleted).

10. Notifications (in-app only)
No external notifications in v1.

In-app notification triggers:

Guest joins: show queue number and status URL.

Guest called: status page turns orange, countdown, vibration, sound.

Guest no-show: status page turns red.

Notification templates stored in Settings for future use.

Templates use placeholders: {queue_number}, {branch_name}, {hold_minutes}.

11. Error Codes
Code	HTTP	Meaning
VALIDATION_ERROR	422	Field validation failed
WAITLIST_DUPLICATE_PHONE	409	Phone already on active waitlist
WAITLIST_NOT_FOUND	404	Waitlist entry not found
WAITLIST_INVALID_STATUS	409	Action not allowed for current status
WAITLIST_CLOSED	409	Waitlist is paused
AUTH_INVALID_PIN	401	PIN incorrect
AUTH_TOKEN_EXPIRED	401	JWT expired or invalid
AUTH_RATE_LIMITED	429	Too many login attempts
TABLE_NOT_FOUND	404	Table not found
TABLE_NOT_AVAILABLE	409	Table not available
SETTINGS_NOT_FOUND	404	Settings not found
CONFLICT	409	Conflict with another change
RATE_LIMITED	429	Too many requests
INTERNAL_ERROR	500	Unhandled error
BRANCH_NOT_FOUND	404	Branch not found
NETWORK_ERROR	—	Frontend-only network error

Error response shape:
{
  "error": {
    "code": "WAITLIST_DUPLICATE_PHONE",
    "message": "Phone already on waitlist",
    "details": { "queue_number": "A001" }
  }
}

12. API Summary
Public
GET /api/v1/public/branches/{branch_id}

GET /api/v1/public/branches/{branch_id}/board

POST /api/v1/branches/{branch_id}/waitlist

GET /api/v1/waitlist/{queue_number}

POST /api/v1/waitlist/{queue_number}/cancel

Auth
POST /api/v1/auth/login

POST /api/v1/auth/change-pin

Staff
GET /api/v1/staff/waitlist

POST /api/v1/staff/waitlist/{id}/call

POST /api/v1/staff/waitlist/{id}/seat

POST /api/v1/staff/waitlist/{id}/no-show

POST /api/v1/staff/waitlist/{id}/restore

POST /api/v1/staff/waitlist/{id}/revert

POST /api/v1/staff/waitlist/{id}/cancel

POST /api/v1/staff/waitlist/{id}/edit

POST /api/v1/staff/waitlist/reorder

GET /api/v1/staff/tables

PATCH /api/v1/staff/tables/{id}

GET /api/v1/staff/dashboard

Admin
GET /api/v1/admin/settings

PATCH /api/v1/admin/settings

GET /api/v1/admin/tables

POST /api/v1/admin/tables

PATCH /api/v1/admin/tables/{id}

DELETE /api/v1/admin/tables/{id}

POST /api/v1/admin/reset

Health
GET /health

13. Time and Timezone
Store all timestamps in UTC.

Display in Asia/Taipei.

Date format: 2026-09-10.

DateTime format: 2026-09-10 21:00.

24-hour time.

business_date computed from branch timezone and cutoff hour.

remaining_seconds returned by backend for CALLED entries.

Frontend does not compute time differences.

14. Concurrency
DB unique index on (branch_id, business_date, queue_prefix, seq).

DB unique index on (branch_id, label) for tables.

DB unique index on branch_id for settings.

Duplicate phone checked in transaction.

Seat: update entry + table in one transaction.

No-show: update entry + release table in one transaction.

Reorder: batch update sort_order in one transaction.

Close day: batch update in one transaction.

Concurrent same action: second returns WAITLIST_INVALID_STATUS.

15. Security and Privacy
Phone not logged.

Name not logged.

Token not logged.

PIN hashed with bcrypt.

JWT secret from env.

HTTPS in production (future).

Rate limit on login, join, lookup.

Public board shows only queue number and party size.

Staff list shows masked phone.

Customer status requires token or last 3 digits.

No audit log in v1.

Public endpoints do not require auth.

CORS allows configured origins.

16. Known Limitations
SQLite concurrent writes limited.

Single worker rate limit.

No Alembic.

No CI.

No production deployment.

No structured logging.

No audit log.

No multi-branch UI.

No external notifications.

No reports page.

No dark mode.

No i18n.

No E2E tests.

No concurrency tests.

No optimistic locking.

No soft delete for waitlist entries.

No status change history.

17. Non-Goals
See Section 2.

18. Environment Variables

Backend
Variable	Default	Description
DATABASE_URL	sqlite:///./dev.db	DB connection
JWT_SECRET	change-me-in-production	JWT signing secret
JWT_EXPIRE_HOURS	12	JWT expiry
STAFF_PIN	1234	Initial staff PIN
DEFAULT_BRANCH_ID	1	Default branch
CORS_ORIGINS	http://localhost:5173	Allowed origins
ENV	development	Environment

Frontend
Variable	Default	Description
VITE_API_BASE_URL	/api/v1	API base
VITE_USE_MOCK	true	Use mock API
VITE_BRANCH_ID	1	Default branch
VITE_ENABLE_SOUND	true	Enable sound
VITE_PUBLIC_BASE_URL	``	Public base URL

19. Seed Data
Restaurant: Sunny Bistro

Branch: Taipei Xinyi

Address: No. 123, Example Rd., Xinyi Dist., Taipei City 110, Taiwan

Phone: 02-1234-5678

Hours: 11:00–21:00

Tables: A1–A4 (2 pax), B1–B4 (4 pax), C1–C2 (6 pax)

Waitlist entries:

5 WAITING with different party sizes and notes

1 CALLED with called_at 3 minutes ago

1 SEATED occupying B1

1 NO_SHOW

1 CANCELLED

All business_date = today

Phones: 0900-000-001 to 0900-000-009

Staff PIN: 1234

20. Demo Script
make seed

Open /join?branch=1

Join waitlist

Get A006 and status_url

Open /staff/login, enter 1234

See A006 on waitlist

Click Call

Guest status page turns orange, countdown starts

Click Seat, select A1

Table map shows A1 as OCCUPIED

Open /board/1, see Now Serving

Click Release Table, A1 becomes AVAILABLE

Open /admin/settings, change hold_minutes

21. Definition of Done
All acceptance criteria pass

uv run pytest passes

npm run test passes

No lint errors

PR references issue

Manual verification completed
