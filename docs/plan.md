# Plan

Tech stack: FastAPI / uv / SQLAlchemy 2.0 / Pydantic v2 / SQLite (backend, pytest) + React 18 / Vite / TypeScript / Tailwind / shadcn-ui / TanStack Query / Zustand (frontend, Vitest + RTL); auth single shared PIN -> JWT (HS256). Adopted from `docs/requirements.md`; this is an ADOPTION survey — the 15 open platform issues (label `defined`, legacy ACs already groomed) are adopted into local files, not re-derived.

## phase_5_audit

> Security-audit remediation batch (operator directive 2026-09-13), adopted verbatim from `_docs/issues/T*.md` + platform issues. Legacy AC blocks are the source of truth; per-issue blocks below summarize them.

### t16
- Requirement: _docs/issues/T16.md (platform #71; local docs/issues/t16.md)
- Title: Contract completion: client-facing 404 trio, bodiless 422 docs, Close-Day endpoint
- Acceptance:
  - The 404 trio (legacy client paths) resolves: each is a documented, served endpoint or has zero frontend references
  - Join/seat 422 responses carry the documented contract error envelope in both contract documents
  - Close-Day defined: documented, served endpoint, or an explicit out-of-contract statement in specs.md
  - Conformance sweep test extended to the new contract surface
- Files: _docs/specs.md, _docs/openapi.yaml, backend/app/routers/*, frontend/src/api/*, backend/tests/
- Depends: []
### t17
- Requirement: _docs/issues/T17.md (platform #72; local docs/issues/t17.md)
- Title: Frontend client lifecycle: expires_at honoured, router-driven redirect, shared-UI resource cleanup
- Acceptance:
  - Client stores expiresAt with the token; expiry is treated as logout (hydrated guard + timer -> destroySession); request() refuses a known-expired bearer
  - 401 redirect uses the ROUTES constant + location.assign with an already-on-login guard
  - ONE shared 1Hz ticker replaces per-card useCountdown intervals (WaitlistCard fan-out preserved); SoundToggle reuses one lazily-created AudioContext and closes it on teardown; ConnectionBanner.resetFailure timeout tracked+cleared
- Files: frontend/src/api/client.ts, frontend/src/hooks/useCountdown.ts, frontend/src/components/{WaitlistCard,SoundToggle,ConnectionBanner}.tsx, frontend/src/layouts/StaffLayout.tsx
- Depends: []
### t18
- Requirement: _docs/issues/T18.md (platform #73; local docs/issues/t18.md)
- Title: Response-envelope compliance: contract error envelope on every non-2xx, including router-level refusals
- Acceptance:
  - Uvicorn oversized-request-line 400 and FastAPI router 404 produce the contract error envelope, or are documented as edge-owned with contract-mapping middleware
  - Capacity-reject 422 carries details.fields naming the field (parity with schema-level 422s)
  - Conformance sweep test asserts envelope shape on 401/404/405/409/422/429/500/503 classes
- Files: backend/app/errors.py, backend/app/main.py, _docs/specs.md, backend/tests/
- Depends: []
### t19
- Requirement: _docs/issues/T19.md (platform #74; local docs/issues/t19.md)
- Title: Store contention is a contract outcome: busy/locked maps to a retryable code, WAL or documented single-writer, no silent 500
- Acceptance:
  - sqlite database-is-locked maps to 503 (or contract code) with Retry-After instead of 500 INTERNAL_ERROR
  - Per-request busy timeout shortened from 30s to a documented value; WAL enabled OR single-writer constraint documented at the config site
  - GET that writes (_sweep_expired) audited and moved out of the read path or made contention-safe; measured probe: concurrent external writer -> typed retryable responses, zero 500
- Files: backend/app/errors.py, backend/app/database.py, backend/app/services/staff_waitlist.py, backend/tests/
- Depends: []
### t22
- Requirement: _docs/issues/T22.md (platform #77; local docs/issues/t22.md)
- Title: eslint flat config for eslint 9: author it, get the codebase lint-clean, retire the D-03 AC-6 inversion
- Acceptance:
  - frontend/eslint.config.js exists and npm run lint exits 0 on a clean checkout (react-hooks + typescript-eslint recommended minimum)
  - Violations fixed in the same issue
  - D-03 AC-6 inversion block RE-GROOMED in the same window to assert the now-green state
- Files: frontend/eslint.config.js, frontend/package.json, frontend/src/**, _docs/issues/closed/D-03.md
- Depends: []
### t24
- Requirement: _docs/issues/T24.md (platform #79; local docs/issues/t24.md)
- Title: SQLite-only reality vs PostgreSQL affordance: add the driver and exercise the path, or remove the claim
- Acceptance:
  - DECISION: option A — psycopg2-binary added, PG boot + one-write smoke green, connect_args dialect-aware; OR option B — docs/config stop claiming PG and the code refuses non-sqlite URLs with a clear startup error
  - Either way a fresh clone cannot believe a PG promise that cannot boot
- Files: backend/app/database.py, backend/requirements.txt, README.md, deployment docs, backend/tests/
- Depends: []
### t25
- Requirement: _docs/issues/T25.md (platform #80; local docs/issues/t25.md)
- Title: Repository artifact hygiene: gitignore DB sidecars and local dot-env files; no DB artifacts left in the tree
- Acceptance:
  - gitignore covers test.db, *.db, *.db-journal, *.db-wal, *.db-shm and .env.local/.env.*.local patterns (exact-path where symlink-proofing matters)
  - conftest refuses DATABASE_URL-less runs OR writes only under tmp (D-class decision at groom: refusal preferred)
  - Bare pytest leaves zero untracked files in repo root (measured)
- Files: .gitignore, backend/tests/conftest.py
- Depends: []
### t26
- Requirement: _docs/issues/T26.md (platform #81; local docs/issues/t26.md)
- Title: Security headers on every response class plus CSP, HSTS-ready, cache policy
- Acceptance:
  - ExceptionMiddleware composed INSIDE the headers layer: 500s carry X-Request-ID + nosniff + X-Frame-Options + Referrer-Policy (measured forced-500 probe)
  - CSP shipped on html responses (report-only acceptable first step); X-Request-ID bounded (<=128 chars) with server-generated fallback
  - Cache-Control: no-store on staff/admin and api JSON responses; HSTS emitted behind-the-proxy, setting gated
- Files: backend/app/main.py, backend/app/middleware.py, backend/app/errors.py, backend/tests/
- Depends: []
### t27
- Requirement: _docs/issues/T27.md (platform #82; local docs/issues/t27.md)
- Title: CI from nothing: lint+test+audit workflows on push, frontend build smoke, secret-scan on PRs
- Acceptance:
  - Workflows exist and pass on main: backend ruff + pytest (both TZ clocks), frontend tsc + lint (post-flat-config) + vitest (node 20 pinned)
  - npm audit + pip-audit jobs report advisories; gitleaks/trufflehog secret-scan on PRs
  - Workflow files themselves print no secrets (measured by grep in review)
- Files: .github/workflows/ci.yml, .github/workflows/audit.yml
- Depends: []
### t28
- Requirement: _docs/issues/T28.md (platform #83; local docs/issues/t28.md)
- Title: ready.py readiness tool: closed-set by issue-map intersect platform-state, never by title parse
- Acceptance:
  - closed computed from issue-map.json ids x platform issue-number state (number->id mapping), never title regex
  - SA-era unbracketed titles cannot silently flip an issue back to READY (regression fixture: closed issue with bare title still counts closed)
  - dep-map gap abort replaced by per-issue UNKNOWN-deps report that keeps other issues evaluated
- Files: ../.tq-orchestrator/ready.py (out-of-repo tooling; repo side records the contract)
- Depends: []
### t29
- Requirement: _docs/issues/T29.md (platform #84; local docs/issues/t29.md)
- Title: Integer and length bounds live in schemas: no overflow-500, no out-of-domain values persisted
- Acceptance:
  - Every int request field (branch_id, limit, offset, sort_order, capacity, party_size) carries explicit ge/le in schemas sized to SQLite INTEGER and domain
  - UpdateTableRequest matches CreateTableRequest bounds (capacity ge=1 le=20, label min/max_length)
  - sort_order=9223372036854775808 -> 422 with field details (not 500); negative limit/offset -> 422; service-layer _reject_int becomes belt-and-braces
- Files: backend/app/schemas.py, backend/app/services/tables.py, backend/app/routers/{admin,staff_waitlist}.py, backend/tests/
- Depends: []
### t31
- Requirement: _docs/issues/T31.md (platform #86; local docs/issues/t31.md)
- Title: Staff waitlist list paginates in SQL instead of materialising the full result
- Acceptance:
  - queue_rows applies LIMIT/OFFSET in SQL; total comes from COUNT
  - limit<=0 or offset<0 rejected at schema layer (bounds issue t29)
  - List latency independent of day size (measured N=200 fixture: request cost ~O(limit)); response shape unchanged
- Files: backend/app/services/{staff_waitlist,queue_rows}.py, backend/app/routers/staff_waitlist.py, backend/tests/
- Depends: []

### t13
- Requirement: _docs/issues/T13.md (platform #68; local docs/issues/t13.md)
- Title: FINAL regression gate: every closed-feature QA surface re-passes green after the audit batch
- Acceptance:
  - runacs full-suite green: backend floors >= 274 collected / 272+2 xfailed / 0 failed on both TZ clocks (xfail set unchanged), frontend 228 passed / 27 files (post-major-bump numbers may move — approved new floors must be recorded), tsc 0, lint gates both clean
  - Every fixed issue's own AC re-run, plus attack regression (forged-token 401, ENV-unset boot refusal, PIN-burst 429, header presence on 500, overflow 422, locked -> typed retryable, XSS payloads inert, logout clears all slots) — recorded with measurements
  - No product change by this issue
- Files: _docs/issues/T28* (verification blocks), _docs/state/outputs/
- Depends: [t9, t10, t11, t12, t14, t15, t16, t17, t18, t19, t20, t21, t22, t23, t24, t25, t26, t27, t28, t29, t30, t31]

## phase_6_test_infra

> Test-suite reliability (post-T21). Sources: GitHub issue bodies #91 / #92 (not in the legacy local tree).

### t35
- Requirement: docs/issues/t35.md (body of #91) (platform #91; local docs/issues/t35.md)
- Title: T35 test-infra: drvfs SQLite flake between test_log_hygiene and test_db_atomicity (disk I/O error in setup)
- Acceptance:
  - Full backend suite stable: complete suite (or at minimum test_log_hygiene.py + test_db_atomicity.py together) 10 consecutive runs -> 10 green, no disk I/O error setup failures
  - The fix must not weaken either test's assertions
- Files: backend/tests/test_log_hygiene.py, backend/tests/_db_test_support.py, backend/tests/test_db_atomicity.py, backend/tests/conftest.py
- Depends: []
### t36
- Requirement: docs/issues/t36.md (body of #92) (platform #92; local docs/issues/t36.md)
- Title: T36 test-infra: test_rate_limit_t23.py XFF tests order-dependent shared limiter state (flake)
- Acceptance:
  - 10 consecutive full-suite runs (default random, -p no:randomly, --randomly-seed=42) green with 0 failures in test_rate_limit_t23.py
  - Limiter state reset between tests (fixture or per-test isolation) so the XFF tests are order-independent
  - No product behaviour change (only test isolation is fixed)
- Files: backend/tests/test_rate_limit_t23.py (per issue body; Files section to be pinned at groom)
- Depends: []

## Commands (this host)

Windows host, uv-managed CPython 3.12 (backend), Node 22 (frontend). WSL is NOT available for the toolchain on this host.

- Backend test: `cd backend && uv run pytest tests -q -p no:randomly` — baseline: 331 passed, 2 xfailed
- Frontend test: `cd frontend && npx vitest run` — baseline: 30 files / 244 passed
- Note: t35 (drvfs SQLite flake) and t36 (XFF rate-limit state) are test-infra flakes of the backend suite; expect flake-related reds on full-suite runs until phase_6_test_infra lands.

## Processing order

Serial (MAX_SLOTS=1).

- `phase_5_audit`: FIFO by id starting at t16: t16, t17, t18, t19, t22, t24, t25, t26, t27, t28, t29, t31.
- **t13 is EXCLUDED from that FIFO and is processed LAST** — after `phase_6_test_infra` — because t13 is the FINAL regression gate over t9-t31 and must run after t35 (SQLite flake) and t36 (XFF rate-limit tests) land. t13's prio-high label is intentional, but ordering is dependency-driven, not label-driven.
- `phase_6_test_infra`: t35, t36.
- Then t13 (final gate).
