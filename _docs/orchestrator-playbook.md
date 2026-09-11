# Orchestrator playbook (hard-won operating knowledge)

Companion to `_docs/team/orchestrator.md`, which defines the state machine, slots, gates and merge
lifecycle. This file records only what that file does not: how to write ACs that cannot lie, which
implementation traps this stack actually enforces, and how the harness fails. Read it before
grooming anything, and append a ruling line whenever a decision binds future issues.

## 1. Contract precedence

1. `_docs/openapi.yaml` - paths, field names, status codes, and exactly which `error.code` values
   exist. A code that no operation returns is not part of the API contract (`_docs/specs.md`
   section 11 lists such codes explicitly as outside it - never emit them).
2. `_docs/specs.md` - behaviour prose (algorithms, payloads, timing, state machines).
3. `_docs/issues/<ID>.md` narrative - restates the above; if it disagrees, 1 and 2 win.
4. The ```bash AC blocks inside an issue file - the executable spec for that issue. Once groomed
   and landed, AC text and its bash block are FROZEN: SW and QA may tick `- [ ]` -> `- [x]`, never
   edit a claim. If an AC is wrong, that is a ruling the Orchestrator must make and record, not
   something a worker quietly fixes.

Neither specs nor openapi fixes the human-readable `error.message`. Assert `error.code` and
non-empty `message`, never exact message text.

## 2. Grooming: ACs must be executable and two-sided

Every AC is a heading plus one ```bash block that runs from the repo root and prints exactly one
verdict line, `PASS AC-n ...` or `FAIL AC-n ...`. Grading reads the PRINTED line, never the exit
code, so a block that prints nothing is not green - it is silent, and silent is a failure.

Rules that keep ACs honest:

- **Vacuous-green guard.** Every AC that grades a file it expects the issue to create must start
  with `test -f <path> || { echo "FAIL AC-n: <path> not found"; exit 0; }`. Without it a missing
  file prints nothing and can be misread as green.
- **No hardcoded worktree or absolute paths.** Blocks run from the repo root of whatever checkout
  is being graded.
- **Clean up** any temp SQLite file, and never write outside the repo.
- `accheck.py` (private tooling) must report 0 findings: heading sequence, one block per AC, at
  least 8 level-2 sections.
- **Two-sided probe (mandatory before landing a backend groom).** (a) Run the ACs with nothing
  implemented: every block must print its FAIL guard, and the baseline must be all-red.
  (b) Write a THROWAWAY implementation plus tests, run again, and require all-green. (c) Delete the
  throwaway, keep the probe copy as evidence, and land only the issue file.
  Skipping (b) hides green-UNREACHABLE ACs; skipping (a) hides green-BY-ACCIDENT ACs. Both have
  happened. Groom-time `Measured today:` lines record the honest red baseline; two ACs may be
  green by design (e.g. a CJK-only guard) and must say so explicitly instead of faking red.

## 3. Environment traps (harness, not product)

- **drvfs cannot host toolchains.** WSL truncates large npm binaries on unpack and cannot exec
  Linux binaries, so every `npm`/`vitest`/`pytest`/`ruff`/`uv` run belongs on an ext4 filesystem.
- `cd` and `export` do not persist between tool calls: repeat them in every command.
- `python` is not on PATH (`python3`, or the project venv's interpreter). `uv` may need
  `PATH="$HOME/.local/bin:$PATH"` or an absolute path.
- A fresh worktree has no venv and no `node_modules`; install before a worker starts, or the worker
  burns its budget on setup.
- **Write-hijack.** Subagent runner processes are Windows-side: a `write`/`edit` tool call targeting
  a Linux-only path does not fail, it silently lands in a phantom tree on the Windows drive.
  Therefore: workers write with bash heredocs only and verify with `wc -l` in the same call; the
  Orchestrator never `write`s to Linux-only paths either (heredoc, or write to the repo side).
- Tool installs belong outside a QA gate. If a step fails on PATH, fix the reference (absolute
  interpreter, venv module form); installing packages inside a gate breaks environment parity.

## 4. Backend implementation rulings (proven, reuse them in grooms and briefs)

These came out of AC probes or QA cycles. Each one has already cost a worker cycle at least once.

- **Errors.** Raise the shared `AppError(code, message=None, status_code=None, details=None)` and
  let the registered handlers render `{"error": {"code", "message", "details"}}`. The payload
  OMITS `details` when empty (an AC requiring `details` unconditionally is unreachable - grade it
  "a dict when present"). `RequestValidationError` maps to 422 `VALIDATION_ERROR` with
  `details.fields`. An unhandled `Exception` becomes 500 `INTERNAL_ERROR` with no traceback leaked.
- **Auth.** `HTTPBearer(auto_error=False)`; `scheme_name` compares case-insensitively
  (`"HTTPBearer"`). JWT is HS256 with `sub="staff"`, `role`, `iat`, `exp`;
  `expires_in == JWT_EXPIRE_HOURS * 3600`, computed once and reused for both the claim and the
  response field, and ACs should force a NON-default hour value so a hardcoded constant fails.
  `expires_in` and the PIN store rules follow `_docs/specs.md` section 3.
- **`Staff` is already an `Annotated` alias** (`Annotated[dict, Depends(get_current_staff)]`). Use
  `staff: Staff`. Writing `Annotated[dict, Depends(Staff)]` makes FastAPI read the payload as a
  request body, so the route answers 422 before authentication runs and every auth 401 becomes
  unreachable. Ruff B008 also forbids `Depends(...)` in argument defaults - use the `Annotated` form.
- **The router enforces its own claims.** The shared dependency validates signature/expiry and the
  presence of `sub` but does not compare `sub` to a role; a route that must reject a guest token has
  to check `sub` itself. Do not assume the shared dependency is a role guard.
- **Never assert the exact `error.message`** (see section 1).
- **Rate limiting (slowapi).** The decorator target must annotate `request: Request` or the app
  fails at import time. FastAPI matches the FIRST registered route, so a scratch probe route with
  the same path silently shadows the AC's own registration - probe routes must be deleted, not
  fixed. The limiter is process-global: in pytest a consumed burst is not undone by
  `limiter._storage.reset()`, while `limiter.enabled = False` does suppress limiting, so a suite
  needs an autouse fixture that disables it and exactly one test that re-enables it. Do not
  `importlib.reload()` the app module in tests: the router keeps the limiter it imported at load
  time, so `app.state.limiter is limiter` then fails.
- **Ruff gotchas in this config.** S106/S105 reject `token_type="bearer"` as a keyword argument and
  a `TOKEN_TYPE = "bearer"` module constant, while dict literals are clean - return a plain dict
  from a route with `response_model=...` and validation still happens. B017 forbids
  `pytest.raises(Exception)` (use the concrete exception). E501 is 100 columns. No Yoda comparisons
  (SIM300), no `%`-formatting (UP031).
- **Password hashing.** Use `bcrypt.checkpw`/`hashpw` directly: `passlib` 1.7.4 with `bcrypt` 5.x
  is broken in this venv. `passlib` and other unlisted packages are dependency additions and belong
  to no issue's scope.
- **SQLAlchemy / SQLite.** `Base.metadata.create_all(engine)` after importing `app.models`. Schema
  check-in/checkout listeners need `event.listen(engine, ...)` plus `event.remove` with the SAME
  callable. `UUID(as_uuid=True)` rejects `str`. pydantic v2 does not coerce `uuid.UUID` to `str`
  (use a `mode="before"` validator). `DateTime(timezone=True)` is stored as a naive UTC string on
  SQLite - reattach UTC before comparing with `datetime.now(UTC)`.
- **Test client.** `TestClient(app, raise_server_exceptions=False)` so the 500 envelope is visible
  instead of raised. Tests run with cwd `backend/`, so repo-level docs are
  `Path(__file__).resolve().parents[2] / "_docs" / "specs.md"`. Importing `app.models` imports
  `app.config`, which fails fast on missing env vars and echoes SQL when `ENV` is `development` -
  AC blocks must set a non-development `ENV` or the echo buries the verdict line.
- **Settings are cached** (`lru_cache`). A test that changes an env var must call the getter's
  `cache_clear()` and reload, then restore. Never widen a production security default (e.g. CORS
  `allow_origins`) to satisfy a test - when both a test and an AC could be fixed, fix the one the
  AC does not own.
- **Model/response typing.** Response models use `ConfigDict(from_attributes=True,
  extra="forbid")`. An enum field that can legitimately be NULL in the DB must be
  `Enum | None = None`: a bare `Enum` with a `None` default cannot validate such a row, which makes
  the AC structurally unreachable. Where an AC checks enum wiring it unwraps `Optional` with
  `get_args`, so the test and the AC assert the same contract.
- **OpenAPI introspection in tests.** Prefer `app.openapi()["paths"]` for path/method enumeration;
  walking `app.routes` and reading `.path` breaks when a mount returns a router object without it.
  Import slowapi's class as `from slowapi import Limiter` (`slowapi.core` does not exist).

## 5. Process rulings

- Groom commits are docs-only and land on `main` before any SW dispatch; an uncommitted groom is
  invisible to a worker because worktrees branch from `origin/main`.
- Rebase (or recreate) an issue branch onto current `main` before dispatch, so the worker's suite
  baseline is the real one. Stale baselines produce false AC failures.
- A worker's completion report is trusted only with a commit sha plus verbatim gate output, and the
  Orchestrator re-verifies: `git rev-parse HEAD`, `git show --name-only HEAD`, its own AC-harness
  run, the suite, the linter, and an English-only scan. A claimed sha can exist without being that
  worker's commit (it happened: the sha was the groom commit and HEAD had not moved).
- A dead or timed-out worker often leaves usable files. Grade what exists before re-dispatching;
  do not trust the worker's own "changed files" summary - confirm with `git status` in the worktree.
- Steering a live worker to read-only is cheaper than letting it write a divergent second version
  after the Orchestrator has committed; the result is an independent second measurement of one sha.
- Mechanical, assertion-preserving test fixes (regex escaping, line wrapping, a probe route
  registration) may be applied by the Orchestrator for a dead worker's deliverable ONLY with a
  recorded ruling. Weakening an assertion is never mechanical.
- Mirror rule: the Platform Issue body is the ENTIRE `_docs/issues/<ID>.md` file, byte-identical,
  verified with the private mirror checker after every merge and after every body update. Sync the
  long-lived checkout to `origin/main` before checking.
- `git reset --hard` on a checkout that may hold uncommitted worker work is forbidden. Salvage to a
  preserve directory first, then `git checkout --` the noise. Line-ending warnings are not content:
  compare per file with `git diff --numstat` before deciding.
- Provider failures look like agent deaths. Verify the worktree for leftovers, probe the model
  endpoint directly, then re-dispatch citing the dead run id. Do not switch a governed pipeline to
  an ad-hoc CLI fallback without the owner's approval.

## 6. Frontend rulings

- Per-file `// @vitest-environment jsdom` pragma rather than a global environment switch.
- Coverage assertions read the numeric reporter output (`statements.pct`), not the printed table.
- `package.json` / lockfile edits are not part of a feature issue's scope.
- Node work happens on ext4 (section 3); a `node_modules` symlink from a warm worktree saves a
  3-minute install.
