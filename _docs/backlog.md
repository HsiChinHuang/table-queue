# Backlog

Work order is topological: every issue appears after all of its `depends`.
`Platform` is the Platform Issue number recorded in `_docs/issue-map.json`.

| ID | Title | Depends | Platform | Status |
|---|---|---|---|---|
| P0-01 | Write _docs/specs.md | [] | #1 | closed |
| P0-02 | Write _docs/ui.md | [P0-01] | #2 | closed |
| P0-03 | Write _docs/openapi.yaml | [P0-01] | #3 | closed |
| P0-04 | Write _docs/testing.md | [P0-01] | #4 | closed |
| P0-05 | Write _docs/deployment.md | [P0-01] | #5 | closed |
| P0-06 | Write _docs/api-examples.md | [P0-03] | #6 | closed |
| P0-07 | Write _docs/demo.md | [P0-01] | #7 | closed |
| P0-08 | Write README.md | [P0-01, P0-03, P0-05] | #8 | closed |
| P0-09 | Write CONTRIBUTING.md | [P0-01] | #9 | closed |
| P0-10 | Write AGENTS.md | [P0-01, P0-09] | #10 | closed |
| P0-11 | Write _docs/plan.md | [P0-01] | #11 | closed |
| F-01 | Setup repo structure | [P0-08, P0-09, P0-10] | #12 | closed |
| F-02 | Init frontend project | [F-01] | #13 | closed |
| F-03 | API client and mock layer | [F-02] | #14 | closed |
| F-04 | Zustand store and query keys | [F-02] | #15 | closed |
| F-05 | Layouts and routing | [F-02] | #16 | closed |
| F-06 | Shared components | [F-02] | #17 | closed |
| F-07 | JoinPage | [F-05, F-06] | #18 | closed |
| F-08 | StatusPage | [F-05, F-06] | #19 | closed |
| F-09 | LookupPage | [F-05, F-06] | #20 | closed |
| F-10 | BoardPage | [F-05, F-06] | #21 | closed |
| F-11 | LoginPage | [F-04, F-05, F-06] | #22 | closed |
| F-12 | WaitlistPage | [F-05, F-06] | #23 | closed |
| F-13 | TablesPage | [F-05, F-06] | #24 | closed |
| F-14 | SettingsPage | [F-05, F-06] | #25 | closed |
| F-15 | Frontend tests | [F-03, F-06, F-07, F-08] | #26 | closed |
| B-01 | Init backend project | [F-01] | #27 | closed |
| B-02 | SQLAlchemy models | [B-01] | #28 | closed |
| B-03 | Pydantic schemas | [B-01] | #29 | closed |
| B-04 | Errors and dependencies | [B-01] | #30 | closed |
| B-05 | Auth endpoints | [B-02, B-03, B-04, B-15] | #31 | closed |
| B-06 | Public endpoints | [B-02, B-03, B-04] | #32 | closed |
| B-07 | Staff waitlist endpoints | [B-02, B-03, B-04, B-06] | #33 | closed |
| B-08 | Staff tables endpoints | [B-02, B-03, B-04] | #34 | closed |
| B-09 | Staff dashboard endpoint | [B-02, B-03, B-04, B-07, B-08] | #35 | closed |
| B-10 | Admin settings endpoints | [B-02, B-03, B-04] | #36 | closed |
| B-11 | Admin tables endpoints | [B-02, B-03, B-04] | #37 | closed |
| B-13 | Seed script | [B-02] | #38 | closed |
| B-12 | Admin reset endpoint | [B-02, B-03, B-04, B-13] | #39 | closed |
| B-14 | Backend tests | [B-05, B-06, B-07, B-08, B-09, B-10, B-11, B-12, B-13] | #40 | closed |
| I-01 | Switch frontend to real API | [B-14, F-15] | #41 | closed |
| I-02 | Verify end-to-end flow | [I-01] | #42 | closed |
| D-01 | Swap mock store for real SQLAlchemy DB | [I-02] | #43 | closed |
| D-02 | Add more tests | [D-01] | #44 | closed |
| D-03 | Verify all tests pass | [D-02] | #45 | closed |
| B-15 | Fix the settings bootstrap INSERT | [B-02, B-04] | #47 | closed |
| F-16 | Ignore pytest artifacts in .gitignore | [F-01] | #48 | closed |
| P0-16 | Register P0-13 in issue-map.json | [P0-11] | #49 | closed |
| D-04 | Prove every AC can fail: vacuity detector for the AC gate | [P0-04] | #50 | closed |
| D-05 | Slim AGENTS.md to Hard rules + Pointers, relocate project content | [P0-09] | #51 | closed |
| D-06 | Fix AC-gate defects found grooming D-04/D-05: merge-blind scope checks, silent failure paths, unpinable rate-limit claims | [D-04, D-05] | #54 | closed |
| D-07 | Re-spec B-05 AC-3 into independently decided assertions | [D-06] | #55 | closed |
| D-08 | Route QA FAIL on docs-type issues to PM, not SW | [P0-04] | #56 | closed |
| D-09 | Make the document index truthful: real grants, guide rows, resolvable paths, ownership rows | [P0-09] | #57 | closed |
| B-17 | Fix cross-module test pollution (test_auth engine rebinding) and pin `-p no:randomly` in suite-wide AC gates | [B-05, B-06] | #58 | closed |
| T7 | Docs hygiene sweep: B-11 paperwork, testing.md counts, Constraints convention, main.py ASCII (owner-approved T6/T7/T10 from the debt register) | [] | #59 | closed |
| T8 | Repair B-11 AC-1 admin-slot set-difference | [] | #61 | closed |
| T9 | Staff PIN integrity: hash on bootstrap, no plaintext env fallback, constant-time | [] | #64 | backlog |
| T10 | JWT secret strength gate: reject published/example secrets and short values at s | [] | #65 | backlog |
| T11 | Guest capability redesign: server-minted unguessable status token, no PII in URL | [] | #66 | backlog |
| T12 | Frontend dependency advisories: dev-server RCE-class and react-router open redir | [] | #67 | backlog |
| T13 | FINAL regression gate: every closed-feature QA surface re-passes green after the | [] | #68 | backlog |
| T14 | Waitlist board render scale: bound the lists or virtualise, replace 3s full-list | [] | #69 | backlog |
| T15 | Mock data out of the shipped bundle: env-gated dynamic import, build-time CI ass | [] | #70 | backlog |
| T16 | Contract completion: client-facing 404 trio, bodiless 422 docs, Close-Day endpoi | [] | #71 | backlog |
| T17 | Frontend client lifecycle: expires_at honoured, router-driven redirect, shared-U | [] | #72 | backlog |
| T18 | Response-envelope compliance: contract error envelope on every non-2xx, includin | [] | #73 | backlog |
| T19 | Store contention is a contract outcome: busy/locked maps to a retryable code, WA | [] | #74 | backlog |
| T20 | ENV fail-open: ENV must be explicit; development-mode reset and SQL echo must no | [] | #75 | backlog |
| T21 | Log hygiene: no PII or tracebacks to stdout, no credentials in query strings, sp | [] | #76 | backlog |
| T22 | eslint flat config for eslint 9: author it, get the codebase lint-clean, retire  | [] | #77 | backlog |
| T23 | Rate limiter actually applies to API routes, honours proxy trust, covers change- | [] | #78 | backlog |
| T24 | SQLite-only reality vs PostgreSQL affordance: add the driver and exercise the pa | [] | #79 | backlog |
| T25 | Repository artifact hygiene: gitignore DB sidecars and local dot-env files; no D | [] | #80 | backlog |
| T26 | Security headers on every response class plus CSP, HSTS-ready, cache policy | [] | #81 | backlog |
| T27 | CI from nothing: lint+test+audit workflows on push, frontend build smoke, secret | [] | #82 | backlog |
| T28 | ready.py readiness tool: closed-set by issue-map intersect platform-state, never | [] | #83 | backlog |
| T29 | Integer and length bounds live in schemas: no overflow-500, no out-of-domain val | [] | #84 | backlog |
| T30 | Frontend session storage: one store, one key, remember-me actually controls pers | [] | #85 | backlog |
| T31 | Staff waitlist list paginates in SQL instead of materialising the full result | [] | #86 | backlog |
