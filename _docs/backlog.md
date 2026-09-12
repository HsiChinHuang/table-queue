# Backlog

Work order is topological: every issue appears after all of its `depends`.
`Platform` is the Platform Issue number recorded in `_docs/issue-map.json`.

| ID | Title | Depends | Platform | Status |
|---|---|---|---|---|
| P0-01 | Write _docs/specs.md | [] | #1 | backlog |
| P0-02 | Write _docs/ui.md | [P0-01] | #2 | backlog |
| P0-03 | Write _docs/openapi.yaml | [P0-01] | #3 | backlog |
| P0-04 | Write _docs/testing.md | [P0-01] | #4 | backlog |
| P0-05 | Write _docs/deployment.md | [P0-01] | #5 | backlog |
| P0-06 | Write _docs/api-examples.md | [P0-03] | #6 | backlog |
| P0-07 | Write _docs/demo.md | [P0-01] | #7 | backlog |
| P0-08 | Write README.md | [P0-01, P0-03, P0-05] | #8 | backlog |
| P0-09 | Write CONTRIBUTING.md | [P0-01] | #9 | backlog |
| P0-10 | Write AGENTS.md | [P0-01, P0-09] | #10 | backlog |
| P0-11 | Write _docs/plan.md | [P0-01] | #11 | backlog |
| F-01 | Setup repo structure | [P0-08, P0-09, P0-10] | #12 | backlog |
| F-02 | Init frontend project | [F-01] | #13 | backlog |
| F-03 | API client and mock layer | [F-02] | #14 | backlog |
| F-04 | Zustand store and query keys | [F-02] | #15 | backlog |
| F-05 | Layouts and routing | [F-02] | #16 | backlog |
| F-06 | Shared components | [F-02] | #17 | backlog |
| F-07 | JoinPage | [F-05, F-06] | #18 | backlog |
| F-08 | StatusPage | [F-05, F-06] | #19 | backlog |
| F-09 | LookupPage | [F-05, F-06] | #20 | backlog |
| F-10 | BoardPage | [F-05, F-06] | #21 | backlog |
| F-11 | LoginPage | [F-04, F-05, F-06] | #22 | backlog |
| F-12 | WaitlistPage | [F-05, F-06] | #23 | backlog |
| F-13 | TablesPage | [F-05, F-06] | #24 | backlog |
| F-14 | SettingsPage | [F-05, F-06] | #25 | backlog |
| F-15 | Frontend tests | [F-03, F-06, F-07, F-08] | #26 | backlog |
| B-01 | Init backend project | [F-01] | #27 | backlog |
| B-02 | SQLAlchemy models | [B-01] | #28 | backlog |
| B-03 | Pydantic schemas | [B-01] | #29 | backlog |
| B-04 | Errors and dependencies | [B-01] | #30 | backlog |
| B-05 | Auth endpoints | [B-02, B-03, B-04, B-15] | #31 | backlog |
| B-06 | Public endpoints | [B-02, B-03, B-04] | #32 | backlog |
| B-07 | Staff waitlist endpoints | [B-02, B-03, B-04, B-06] | #33 | backlog |
| B-08 | Staff tables endpoints | [B-02, B-03, B-04] | #34 | backlog |
| B-09 | Staff dashboard endpoint | [B-02, B-03, B-04, B-07, B-08] | #35 | backlog |
| B-10 | Admin settings endpoints | [B-02, B-03, B-04] | #36 | backlog |
| B-11 | Admin tables endpoints | [B-02, B-03, B-04] | #37 | backlog |
| B-13 | Seed script | [B-02] | #38 | backlog |
| B-12 | Admin reset endpoint | [B-02, B-03, B-04, B-13] | #39 | backlog |
| B-14 | Backend tests | [B-05, B-06, B-07, B-08, B-09, B-10, B-11, B-12, B-13] | #40 | backlog |
| I-01 | Switch frontend to real API | [B-14, F-15] | #41 | backlog |
| I-02 | Verify end-to-end flow | [I-01] | #42 | backlog |
| D-01 | Swap mock store for real SQLAlchemy DB | [I-02] | #43 | backlog |
| D-02 | Add more tests | [D-01] | #44 | backlog |
| D-03 | Verify all tests pass | [D-02] | #45 | backlog |
| B-15 | Fix the settings bootstrap INSERT | [B-02, B-04] | #47 | backlog |
| F-16 | Ignore pytest artifacts in .gitignore | [F-01] | #48 | backlog |
| P0-16 | Register P0-13 in issue-map.json | [P0-11] | #49 | backlog |
| D-04 | Prove every AC can fail: vacuity detector for the AC gate | [P0-04] | #50 | backlog |
| D-05 | Slim AGENTS.md to Hard rules + Pointers, relocate project content | [P0-09] | #51 | backlog |
| D-06 | Fix AC-gate defects found grooming D-04/D-05: merge-blind scope checks, silent failure paths, unpinable rate-limit claims | [D-04, D-05] | #54 | groomed |
| D-07 | Re-spec B-05 AC-3 into independently decided assertions | [D-06] | #55 | groomed |
| D-08 | Route QA FAIL on docs-type issues to PM, not SW | [P0-04] | #56 | groomed |
| D-09 | Make the document index truthful: real grants, guide rows, resolvable paths, ownership rows | [P0-09] | #57 | groomed |
| B-17 | Fix cross-module test pollution (test_auth engine rebinding) and pin `-p no:randomly` in suite-wide AC gates | [B-05, B-06] | #58 | backlog |
| T7 | Docs hygiene sweep: B-11 paperwork, testing.md counts, Constraints convention, main.py ASCII (owner-approved T6/T7/T10 from the debt register) | [] | #59 | backlog |
