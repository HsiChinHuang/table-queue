# TableQueue — Deployment Guide

Version: 0.1.0
Last updated: 2026-09-10

---

## 1. Local Development

### Prerequisites
- Python 3.11+
- `uv` installed
- Node.js 20+
- `make` (optional, but recommended)

### Setup
```bash
make setup
# or manually:
cd backend && uv sync
cd frontend && npm install
npm install

### Run

bash
make dev
# or manually:
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0
cd frontend && npm run dev -- --host

### Seed

bash
make seed
# or:
cd backend && uv run python -m app.seed --reset

### Test

bash
make test
# or:
cd backend && uv run pytest
cd frontend && npm run test

### Access

Frontend: http://localhost:5173

Backend: http://localhost:8000

API docs: http://localhost:8000/docs

Health: http://localhost:8000/health

### Demo URLs

Join: http://localhost:5173/join?branch=1

Board: http://localhost:5173/board/1

Staff: http://localhost:5173/staff/login (PIN: 1234)

Settings: http://localhost:5173/admin/settings

### Mobile Testing

Start with --host to bind to 0.0.0.0.

Find your local IP (ipconfig / ifconfig).

Open http://<your-ip>:5173/join?branch=1 on phone.

Phone and computer must be on the same Wi-Fi.

### CORS

Backend reads CORS_ORIGINS.

Default: http://localhost:5173.

Add local IP if testing on phone: http://192.168.x.x:5173.

## 2. Environment Variables
### Backend (backend/.env)
Variable	Default	Required	Description
DATABASE_URL	sqlite:///./dev.db	yes	DB connection string
JWT_SECRET	change-me-in-production	yes	JWT signing secret
JWT_EXPIRE_HOURS	12	no	JWT expiry in hours
STAFF_PIN	1234	yes	Initial staff PIN
DEFAULT_BRANCH_ID	1	no	Default branch
CORS_ORIGINS	http://localhost:5173	no	Comma-separated origins
ENV	development	no	development / test / production
### Frontend (frontend/.env)
Variable	Default	Description
VITE_API_BASE_URL	/api/v1	API base path
VITE_USE_MOCK	true	Use mock API
VITE_BRANCH_ID	1	Default branch
VITE_ENABLE_SOUND	true	Enable sound
VITE_PUBLIC_BASE_URL	``	Public base URL (QR code, share links)
### Notes
.env is gitignored.

.env.example is committed.

Frontend VITE_ vars are bundled into the client. Never put secrets there.

ADMIN_PIN is not used in v1; single shared PIN.

## 3. Database
### v1
SQLite file at backend/dev.db.

Created automatically on first run.

Schema created with Base.metadata.create_all.

No Alembic in v1.

Schema change: delete dev.db and re-run make seed.

### Default Data
Restaurant(id=1, name="Sunny Bistro")

Branch(id=1, name="Taipei Xinyi", timezone="Asia/Taipei", business_day_cutoff_hour=4)

Settings(branch_id=1, hold_minutes=10, avg_seat_minutes=15, queue_prefix="A", is_waitlist_open=True)

No tables created by default; use seed or Settings page.

### Future PostgreSQL
Set DATABASE_URL=postgresql+psycopg://user:pass@host/db.

No code changes needed.

Add Alembic before production.

Add pool_size=5, max_overflow=10.

### Backup
v1: copy dev.db.

Future: use managed DB snapshots.

## 4. Future Deployment Notes
### Frontend
Vercel / Netlify / Cloudflare Pages.

Build command: npm run build.

Output: dist/.

Set VITE_API_BASE_URL to backend URL.

Set VITE_PUBLIC_BASE_URL to frontend URL.

### Backend
Railway / Render / Fly.io / VPS.

Start command: uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2.

Set all env vars.

Set ENV=production.

Set CORS_ORIGINS to frontend URL.

### Database
Managed PostgreSQL.

Add Alembic migrations.

Enable backups.

### HTTPS
Provided by hosting platform.

Required for production.

### Reverse Proxy
If behind proxy, read X-Forwarded-For for rate limit.

Configure uvicorn --proxy-headers.

### Logging
v1: stdout.

Future: JSON logs with structlog, log rotation.

### Rate Limit
v1: in-memory, single worker.

Future: Redis-backed for multi-worker.

### Workers
v1: 1 worker.

Future: --workers 2 or more.

## 5. Known Limitations
SQLite concurrent writes limited.

Single worker rate limit.

No Alembic.

No CI.

No production deployment in v1.

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

## 6. Troubleshooting
### Frontend can't reach backend
Check backend is running on port 8000.

Check Vite proxy in vite.config.ts.

Check VITE_API_BASE_URL.

Check CORS.

### Phone can't reach local dev
Use --host for both Vite and uvicorn.

Add local IP to CORS_ORIGINS.

Check firewall.

### Database locked
SQLite issue under concurrent writes.

Restart backend.

Delete dev.db and re-seed if needed.

### JWT expired
Frontend auto-redirects to login.

Log in again with PIN.

### Forgot PIN
Stop backend.

Set STAFF_PIN in .env.

Delete staff_pin_hash in DB, or reset DB.

Restart backend.
