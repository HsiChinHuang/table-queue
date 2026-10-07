# Closed Issues Index

Runtime-maintained by Orchestrator.

| ID | Title | Closed At | Retries | Merge Commit |
|---|---|---|---|---|
| B-10 | Admin settings endpoints | 2026-09-12T13:10:00Z | sw=3 qa=3 (pm=0) | 5d7e85113d0fbf04d5c577f133096e74ffc4d87e (MF-1 merge carries the B-10 payload) |
| MF-1 | MERGE-FIX: B-10 (main.py mount sequence + issue-mirror union) | 2026-09-12T13:10:00Z | pm=3 sw=2 qa=1 | 5d7e85113d0fbf04d5c577f133096e74ffc4d87e |
| B-17 | Fix cross-module test pollution and pin -p no:randomly | 2026-09-12T13:24:00Z | pm=2 sw=5 qa=6 | 36b80f4a60a7b23de903fc8dfe3f7b97b2f8270e |
| B-12 | Admin reset endpoint | 2026-09-12T17:49:00Z | sw=1 qa=1 | 445e85a4eac8d9abd6370319fe666f5f5b1ef788 |
| T8 | Repair B-11 AC-1 admin-slot set-difference | 2026-09-12T19:37:55Z | pm=2 sw=2 qa=1 (sw r2 timeout, work complete, not charged) | e5e4817d3097f88b9e65aa96098f9c46aa95caf3 |
| B-07 | Staff waitlist endpoints | 2026-09-12T19:41:54Z | pm=7 sw=4 qa=2 (r1 stale-abort; r4 timeout uncharged) | 341361f48769d7ca72b04b48cc28fcb85e5613ca |
| B-09 | Staff dashboard endpoint | 2026-09-12T21:22:04Z | pm=2 sw=2 qa=1 (two lane timeouts on the timer-thread spin, root-caused) | e4a127756fa5c5632ea027fe043ec034c88b4470 |
| T7 | Docs hygiene sweep: B-11 paperwork, testing.md counts, Constraints convention, main.py ASCII | 2026-09-13T02:25:00Z | pm=4 (r1 rejected, r2 groom, r4+4b micro-repairs) sw=2 (r2 REJECTED-then-reverted, accepted at b99e707) qa=1 | 50012be01b258fa63d57724d384095a2bfe75dda |
| B-14 | Backend tests | 2026-09-13T03:25:00Z | pm=4 sw=2 qa=1 (+MF-2 merge-fix cycle) | d584cb7841bd313dd6f667d6414247940cfca139 (MF-2 merge carries the B-14 payload; qa-failed at 04291af was the conflict tree-condition, resolved by MF-2) |
| MF-2 | MERGE-FIX: B-14 (testing.md test-file listing) | 2026-09-13T03:25:00Z | pm=1 sw=1 qa=1 | d584cb7841bd313dd6f667d6414247940cfca139 |
| I-01 | Switch frontend to real API | 2026-09-13T05:05:00Z | pm=1 sw=1 qa=1 | c3fc7030bc383d1c9b401b5b492014a224fc8e2a |
| I-02 | Verify end-to-end flow | 2026-09-13T06:20:00Z | pm=1 sw=1 qa=1 | a7244c2b30a2735a897a5b84939f9a3b70ca50bb |
| D-01 | Swap mock store for real SQLAlchemy DB | 2026-09-13T07:25:00Z | pm=1 sw=1 qa=1 | 1dd00d85f37a0d545490a5f3f03cb61650ab2bcb |
| D-02 | Add more tests | 2026-09-13T12:05:00Z | pm=3 sw=1 qa=1 | 160ab19c953fd0fa820c14ee32419c89de816107 |
| D-03 | Verify all tests pass (final verification gate) | 2026-09-13T16:20:00Z | pm=2 sw=1 qa=1 (qa r1 ceiling-death, inventory-resume, zero loss) | d5d97d74587e0a32dca485ac17535ff0102e1564 |
| T10 | JWT secret strength gate: reject published/example secrets and short values at startup | 2026-09-14T04:40:00Z | pm=1 sw=1 qa=1 | 23efdd5c34ba071048005d716689d158305d6c93 |
| T32 | Frontend speaks the published contract: real API integration works with VITE_USE_MOCK=false | 2026-09-14T08:02:52Z | n/a (pre-log-window) | 2bf0942eb79a21395519d0d3d5e5ce984b8e623d |
| T33 | Run surface actually runs: make seed/dev/test-backend resolve an interpreter on this machine | 2026-09-14T08:35:15Z | n/a (pre-log-window) | 376dd5f80bf2afd28b1de47ba22d365ec287ec52 |
| T9 | Staff PIN integrity: hash on bootstrap, no plaintext env fallback, constant-time compare, rotation revokes tokens | 2026-10-03T11:05:00Z | pm=2 (r2 probe repair) sw=2 (r2 timeout-resume) qa=2 (r1 FAIL implementation + timeout-resume; r2 PASS) | 62dc0742da1f00a49ab018276522d4a0b1742815 |
| T20 | ENV fail-open: ENV must be explicit; development-mode reset and SQL echo must not be reachable by default | 2026-10-03T14:30:00Z | pm=1 sw=4 (multiple timeout-resumes) qa=1 (PASS with diff-sanity note) | 6de23b32160bc91d52c3f69a8ea54e21222cf365 |
| T12 | Frontend dependency advisories: dev-server RCE-class and react-router open redirect to fixed versions | 2026-10-03T21:00:00Z | pm=1 sw=1 qa=1 (5/5 AC PASS) | 5684160ff661bbc533b89f37d56cdcbe2a1331a7 |
| T21 | Log hygiene: no PII or tracebacks to stdout, no credentials in query strings, specs 593-598 honoured | 2026-10-04T06:14:00Z | pm=1 (reached_state line omitted — process blemish) sw=1 qa=1 (5/5 AC PASS) | bf3d643a9d8a99a77bca83a02f01097909625ea4 |
| T23 | Rate limiter actually applies to API routes, honours proxy trust, covers change-pin, and states its memory bound | 2026-10-04T13:32:51Z | pm=2 (r1 groom + r1 AC-suggestion re-groom) sw=1 qa=1 (qa r1 500 config error, not charged; r2 PASS) | 402fa34d0d4b305f557431323db0420396c399a6 |
| T30 | Frontend session storage: one store, one key, remember-me actually controls persistence, real logout | 2026-10-04T22:17:17Z | pm=2 (r1 groom + r1 AC-suggestion re-groom, AC-2 null-guard) sw=1 qa=1 (5/5 AC PASS) | a144d658c528f56b5acc65b485f761e647b6cc6e |
| T11 | Guest capability redesign: server-minted unguessable status token, no PII in URLs | 2026-10-05T04:52:03Z | pm=1 sw=1 qa=1 (6/6 AC PASS; post-merge 1 known flake [FLAKY_TEST] test_log_hygiene, T35#91 family) | fdd9a3f6ca6b289e408808109b4ca01710854736 |
| T14 | Waitlist board render scale: bound the lists or virtualise, replace 3s full-list refetch | 2026-10-05T11:51:04Z | pm=1 (timed out at 4h after substantive work; orch set groomed label) sw=1 (missed qa-ready label; orch set) qa=1 (5/5 AC PASS; 1 known flake [FLAKY_TEST] test_log_hygiene T35#91; pre-existing tsc error staffStore.ts noted, out of scope) | dd6d8eeafb6dd2662488f1ad6c68b9fac1cb1190 |
| T15 | Mock data out of the shipped bundle: env-gated dynamic import, build-time CI assertion, seed PIN not a literal | 2026-10-05T20:47:20Z | pm=1 sw=1 (1 [CONSTRAINT VIOLATION REQUEST] staffStore.ts one-line tsc fix, accepted) qa=1 (3/3 AC PASS; no flakes) | 1487e8415d1a1ab7df41debb98b3f1cd168a566d |
| T34 | T34 Integration acceptance gate: a seeded store plus both servers complete the documented demo unattended | 2026-09-15T05:26:24Z | legacy | legacy (gate closed by orchestrator on main e9d69be) |
| t16 | Contract completion: client-facing 404 trio, bodiless 422 docs, Close-Day endpoint | 2026-10-07T08:54:11Z | pm=1 (env: worktree venv 3.13->3.12 rebuild) | 52766eae973e97a1b6b19b6333660f6688f3c1a2 |
