# Backlog

Adopted 2026-10-06 (framework commit 34591cc). 15 open platform issues (HsiChinHuang/table-queue), all label `defined`; legacy ACs adopted verbatim into `docs/issues/`. Processing order is serial (MAX_SLOTS=1), phase_5_audit FIFO from t16, t13 LAST after phase_6_test_infra — see `docs/plan.md` → Processing order.

| ID | Title | Depends | Platform | Status |
|---|---|---|---|---|
| t13 | FINAL regression gate: every closed-feature QA surface re-passes green after the audit batch | t9, t10, t11, t12, t14, t15, t16-t31 (see docs/issues/t13.md) | 68 | defined |
| t16 | Contract completion: client-facing 404 trio, bodiless 422 docs, Close-Day endpoint | - | 71 | closed |
| t17 | Frontend client lifecycle: expires_at honoured, router-driven redirect, shared-UI resource cleanup | - | 72 | closed |
| t18 | Response-envelope compliance: contract error envelope on every non-2xx, including router-level refusals | - | 73 | closed |
| t19 | Store contention is a contract outcome: busy/locked maps to a retryable code, WAL or documented single-writer, no silent 500 | - | 74 | defined |
| t22 | eslint flat config for eslint 9: author it, get the codebase lint-clean, retire the D-03 AC-6 inversion | - | 77 | defined |
| t24 | SQLite-only reality vs PostgreSQL affordance: add the driver and exercise the path, or remove the claim | - | 79 | defined |
| t25 | Repository artifact hygiene: gitignore DB sidecars and local dot-env files; no DB artifacts left in the tree | - | 80 | defined |
| t26 | Security headers on every response class plus CSP, HSTS-ready, cache policy | - | 81 | defined |
| t27 | CI from nothing: lint+test+audit workflows on push, frontend build smoke, secret-scan on PRs | - | 82 | defined |
| t28 | ready.py readiness tool: closed-set by issue-map intersect platform-state, never by title parse | - | 83 | defined |
| t29 | Integer and length bounds live in schemas: no overflow-500, no out-of-domain values persisted | - | 84 | defined |
| t31 | Staff waitlist list paginates in SQL instead of materialising the full result | - | 86 | defined |
| t35 | T35 test-infra: drvfs SQLite flake between test_log_hygiene and test_db_atomicity (disk I/O error in setup) | - | 91 | defined |
| t36 | T36 test-infra: test_rate_limit_t23.py XFF tests order-dependent shared limiter state (flake) | - | 92 | defined |

Closed archive: 27 closed issues (T7, T8, T9, T10, T11, T12, T14, T15, T20, T21, T23, T30, T32, T33, T34 + legacy B/D/I/MF rows) live in `docs/issues/closed/` — see `docs/issues/closed/index.md` (Closed At / Retries / Merge Commit).
