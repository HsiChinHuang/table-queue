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


---

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- `make` (optional)

### Setup

```bash
make setup
```

Or manually:

```bash
cd backend && uv sync
cd frontend && npm install
npm install
```

Run

```bash
make dev
```

Or in two terminals:

```bash
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0
cd frontend && npm run dev -- --host
```

Seed

```bash
make seed
```

Test

```bash
make test
```

Or separately:

```bash
cd backend && uv run pytest
cd frontend && npm run test
```

## Development

### Access

Frontend: http://localhost:5173

Backend: http://localhost:8000

API docs: http://localhost:8000/docs

Health: http://localhost:8000/health

### Demo URLs

Join: http://localhost:5173/join?branch=1

Board: http://localhost:5173/board/1

Staff login: http://localhost:5173/staff/login (PIN: 1234)

Settings: http://localhost:5173/admin/settings

### Mobile Testing

Start with --host to bind to 0.0.0.0. Find your local IP (ipconfig / ifconfig) and open http://<your-ip>:5173/join?branch=1 on your phone. Phone and computer must be on the same Wi-Fi.

Add your local IP to CORS_ORIGINS in backend/.env.

### Makefile Targets

Target	Description
make setup	Install backend and frontend deps
make dev	Run backend and frontend together
make backend	Run backend only
make frontend	Run frontend only
make seed	Reset and seed database
make test	Run all tests
make test-backend	Run backend tests
make test-frontend	Run frontend tests
make lint	Lint frontend
make format	Format frontend
## Environment Variables

Backend (backend/.env)
Variable	Default	Description
DATABASE_URL	sqlite:///./dev.db	DB connection
JWT_SECRET	change-me-in-production	JWT signing secret
JWT_EXPIRE_HOURS	12	JWT expiry
STAFF_PIN	1234	Initial staff PIN
DEFAULT_BRANCH_ID	1	Default branch
CORS_ORIGINS	http://localhost:5173	Allowed origins
ENV	development	Environment
Frontend (frontend/.env)
Variable	Default	Description
VITE_API_BASE_URL	/api/v1	API base path
VITE_USE_MOCK	true	Use mock API
VITE_BRANCH_ID	1	Default branch
VITE_ENABLE_SOUND	true	Enable sound
VITE_PUBLIC_BASE_URL	``	Public base URL
Copy .env.example to .env in both backend/ and frontend/.

## Demo

See _docs/demo.md for the full walkthrough.

Quick demo:

make seed

Open http://localhost:5173/join?branch=1 and join

Open http://localhost:5173/staff/login with PIN 1234

Call, seat, release, close day

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