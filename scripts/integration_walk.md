# Integration Walk Runner Spec

**Purpose**: Step/assertion table for SW to implement `scripts/integration_walk.py`. This is a SPEC, not code.

**Target**: Unattended integration gate that walks `_docs/demo.md` end-to-end through the vite-proxied frontend origin.

## Prerequisites

- Backend server running on configured port (default 8000)
- Frontend server running on configured port (default 5173) with vite proxy to backend
- `VITE_USE_MOCK=false` in frontend env
- Seeded store with at least one WAITING entry (or join creates one)

## Step/Assertion Table

| Step ID | Demo Step | Assertion | Expected | Notes |
|---------|-----------|-----------|----------|-------|
| S1 | Join Waitlist | POST /api/v1/branches/1/waitlist → 201 | 201, response contains `status_token`, `queue_number`, `status_url` | Body: name, phone (0900-000-099), party_size, note |
| S2 | Status Page Load | GET /api/v1/waitlist/{queue_number}?token={status_token} → 200 | 200, response contains status, party_size, waiting_ahead | Must include token query param |
| S3 | Status Without Factor | GET /api/v1/waitlist/{queue_number} → 422 | 422 | No token or phone_last3 |
| S4 | Cancel With Factor | POST /api/v1/waitlist/{queue_number}/cancel with {token} → 200 | 200, status becomes CANCELLED | Body must include token |
| S5 | Cancel Without Factor | POST /api/v1/waitlist/{queue_number}/cancel with {} → 422 | 422 | No token in body |
| S6 | Staff Login | POST /api/v1/auth/login with {pin: "1234"} → 200 | 200, response contains access_token | |
| S7 | Staff Waitlist | GET /api/v1/staff/waitlist with JWT → 200 | 200, response contains items array | |
| S8 | Call Entry | POST /api/v1/staff/waitlist/{id}/call with JWT → 200 | 200, status becomes CALLED | |
| S9 | Status After Call | GET /api/v1/waitlist/{queue_number}?token={status_token} → 200 | 200, status is CALLED, remaining_seconds present | |
| S10 | Seat Entry | POST /api/v1/staff/waitlist/{id}/seat with {table_id} → 200 | 200, status becomes SEATED | |
| S11 | Table Status | GET /api/v1/staff/tables with JWT → 200 | 200, table shows OCCUPIED | |
| S12 | Release Table | POST /api/v1/staff/tables/{id}/release with JWT → 200 | 200, table becomes AVAILABLE | |
| S13 | Public Board | GET /api/v1/public/branches/1/board → 200 | 200, response contains current_called, next_up | |
| S14 | Settings Read | GET /api/v1/admin/settings with JWT → 200 | 200, response contains hold_minutes | |
| S15 | Settings Write | PATCH /api/v1/admin/settings with JWT {hold_minutes: 12} → 200 | 200, subsequent read shows 12 | |

## Output Requirements

- Log file at documented artifact path (e.g., `/tmp/tq-walk.log` or `_docs/state/outputs/`)
- Final line: `RESULT=PASS` or `RESULT=FAIL`
- Each step logs: `STEP {id}: {status} (rc={code})`
- Exit code: 0 if all steps pass, 1 if any step fails

## Environment Variables

- `BACKEND_URL`: Backend base URL (default: http://localhost:8000)
- `FRONTEND_URL`: Frontend base URL (default: http://localhost:5173)
- `VITE_USE_MOCK`: Must be "false" (log error if not)
- `STAFF_PIN`: For staff login (default: 1234)

## Failure Modes

| Condition | Exit | Log |
|-----------|------|-----|
| Runner script missing | N/A | AC-2/5/6/7 fail with `runner_missing` |
| Backend not responding | 1 | `BACKEND_UNREACHABLE` |
| Frontend not responding | 1 | `FRONTEND_UNREACHABLE` |
| Mock mode detected | 1 | `MOCK_MODE_ENABLED` |
| Step assertion fails | 1 | `STEP {id}: FAILED (expected {x}, got {y})` |
| All steps pass | 0 | `RESULT=PASS` |

## Notes for SW Implementation

1. Use `requests` library for HTTP calls
2. Parse `status_token` from join response, use for subsequent status/cancel calls
3. Store JWT from login for staff endpoints
4. Log all requests/responses for debugging
5. Implement kill-on-exit trap for any spawned processes
6. AC-1b pairing proof: join through proxied frontend, verify row appears on configured backend port
