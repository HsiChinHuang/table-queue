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
- **A negative control must be proven to move the AC before it is used as evidence.** Falsification
  that leaves the AC green proves nothing about the AC; it proves the AC cannot see the mutation. On
  B-05 the Orchestrator's own planned control (`5/minute` -> `5/hour`) left AC-6 green, because a
  fixed-window counter is indistinguishable inside one test window (measured: both give
  `401,401,401,401,401,429`; 30 rapid attempts give 30x429). Where an AC provably cannot pin a number,
  the AC's own prose must say so rather than implying it does.
- **Every failure path prints its own `FAIL AC-n:` token.** A block that prints a bare measurement
  (`missing=/api/v1/auth/login:POST`) is graded silent, which is treated as not-green and is invisible
  as a defect. This recurred in the Orchestrator's own B-05 AC-1 - groom-time audit: grep every AC body
  for a `print(`/`echo` that lacks its own `AC-n` token.
- **Two-sided probe (mandatory before landing a backend groom).** (a) Run the ACs with nothing
  implemented: every block must print its FAIL guard, and the baseline must be all-red.
  (b) Write a THROWAWAY implementation plus tests, run again, and require all-green. (c) Delete the
  throwaway, keep the probe copy as evidence, and land only the issue file.
  Skipping (b) hides green-UNREACHABLE ACs; skipping (a) hides green-BY-ACCIDENT ACs. Both have
  happened. Groom-time `Measured today:` lines record the honest red baseline; two ACs may be
  green by design (e.g. a CJK-only guard) and must say so explicitly instead of faking red.
- **The throwaway side of the two-sided probe must be CONTRACT-VISIBLE, not merely mounted.** A
  block that registers a probe under its own namespace and "prefers the contract route when
  mounted" can print PASS on the groomer's tree while the contract route is invisible through the
  venv's editable-install `sys.path` (the long-lived checkout answers the import). Three shapes
  have bitten us, all groom defects: (i) the block fires the contract route first and asserts the
  probe route's view of the same row, so a spec-correct 409-on-replay can never go green (B-07
  AC-8/11/12); (ii) the block builds `TestClient(app)` with no `lifespan=`, so `bootstrap_defaults`
  never runs and its own probe answers 500 before any handler exists - baseline-pass /
  feature-fail is the tell (B-10 AC-8/11); (iii) `getattr(obj, 'x', DEFAULT)` where the stub's
  `__getattr__` raises never reaches DEFAULT - Python evaluates the default eagerly, then the call
  raises - so the fallback branch is dead code and the AC is permanently red on any tree (B-10
  AC-1/AC-5). After (b), read the block's own PASS string, not only its verdict token: a PASS
  carrying a scope disclaimer (`answered 404 on this tree`, `not measured here`,
  `probe-namespaced`) measured nothing about production.
- **Do not pin source-text LOCATIONS in a file another open issue touches.** An AC that greps "no
  `CONFLICT` token appears in `services/tables.py`" and a sibling AC that greps "the refusal lives
  in `services/tables.py`" are unsatisfiable-by-construction once both branches merge (B-08 AC-12
  vs B-11 AC-5/8/9; the SW resolved it only by relocating the code string into helper modules).
  Grep BEHAVIOR (status/code/envelope), not where a literal sits. A Constraints block whose file
  list says "Nothing else" must allow `services/*` whenever the ACs force file-collision
  gymnastics (B-08, B-10 and B-12 all exceeded their lists while their ACs stayed green).
- **Do not assert exact error-message text** unless the message appears in `openapi.yaml` or
  `specs.md`. An AC literal for a 500 message no contract documents (`Internal server error`)
  silently overrode the shipped render path (B-10 AC-10). Codes and statuses are contract; prose
  is not. When a frozen AC already carries such a literal, the AC wins and the groom defect is
  logged, not argued.

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
- **Dispatch budgets are part of the brief.** The subagent default is 30 minutes and it is too short
  for a QA gate or a full groom: three children (two QA gates + one PM) timed out at exactly that
  default on one mission, after 100+ tool calls of real measurement, and none posted a verdict - a
  total loss of expensive work. Pass `timeoutMs` explicitly (60 min for a gate, 50 for a groom) and
  write a verdict-first protocol into the brief: post the verdict and label inside the first 15
  minutes, then put extra probes in a second comment. A partial posted verdict is recoverable.
- **Recover a timed-out child's transcript before re-dispatching.** The session jsonl under
  `~/.pi/agent/sessions/.../run-0/session.jsonl` holds every tool result; extracting the `toolResult`
  text recovered both gates' central mutations. Save it to a preserve file, then re-run the SAME role
  with the dead run id, the failure reason, and the recovered evidence so the child does not redo it.
  Say explicitly which probes are already done and must not be repeated.
- **A child's dependency claim is a claim, not a fact.** A B-06 groom shipped `## Blocked by B-15
  (measured, not inferred)` over a dependency that `git merge-base --is-ancestor` refutes - B-15 was
  already merged and its test passed on the groom's own tree. Verify blockers against `origin/main`
  before dispatching an SW on the strength of them, and route the correction to a PM child: an issue
  file's prose is PM-owned even when the Orchestrator caught the error.
- **A child's `write`/`edit` tools are Windows-rooted even when its bash runs in WSL:** a tool call
  to `/home/te/...` silently lands at `C:\home\te\...` (a ghost tree; the call returns "Successfully
  wrote", the child's own bash cannot see it, so it re-reads empty dirs and starts `find /mnt`).
  All child-visible WORKTREES must live on drvfs (`<repo>/../wt/<ID>`: bash sees `/mnt/c/...`, tools
  see `C:/...` - one file, verified by writing through one view and reading through the other).
  `/home/te/...` stays valid for bash-only needs: DATABASE_URL, TMPDIR, scratch, invoking runacs.py.
  When a child reports "I wrote the file but it is not there", suspect this before suspecting the
  child. Ghost output is recoverable under `/mnt/c/home/te/tq/...` - recover and migrate; never make
  the child rewrite from memory.
- **Test-model children drift; watch the model name.** Both children in one session ran on a
  Qwen-flash test model via ollama: 60-123 tool calls, minutes of exploration, zero file output,
  `find /mnt`-class commands, heavy steering needed. A weak child is still useful as a pair of
  hands - run the ACs, commit when told - but the Orchestrator must pre-resolve its open questions
  into the steer as measured facts, and must read "file not found" + one very long bash tool as a
  path-migration event, not as idleness.
- Provider failures look like agent deaths. Verify the worktree for leftovers, probe the model
  endpoint directly, then re-dispatch citing the dead run id. Do not switch a governed pipeline to
  an ad-hoc CLI fallback without the owner's approval.

## 6. Frontend rulings

- Per-file `// @vitest-environment jsdom` pragma rather than a global environment switch.
- Coverage assertions read the numeric reporter output (`statements.pct`), not the printed table.
- `package.json` / lockfile edits are not part of a feature issue's scope.
- Node work happens on ext4 (section 3); a `node_modules` symlink from a warm worktree saves a
  3-minute install.

## 7. Harness tools (private scripts, specified so they can be rebuilt)

The Orchestrator keeps its helpers outside the repo, alongside a token file that must never be
committed. No credential, hostname or absolute path is recorded here. Their behaviour is specified so a rebuilt harness is equivalent to the lost one.

| Tool | Contract |
|---|---|
| platform API helper | `<METHOD> <path> [json-body-file\|-]` against the REST API with an API-version header; prints the body then the HTTP status to stderr. Labels are set with `PATCH /repos/<repo>/issues/<n>` carrying `{"labels":[...]}` - the `/labels` subresource 404s. Responses can come back empty transiently: retry before concluding failure. Quote query strings containing `&`. |
| AC harness | `runacs <issue-file> [--cwd DIR] [--only AC-n ...]`. Extracts one ```bash block per `- [ ] **AC-n**` heading, runs each in its own process from the repo root with a per-block timeout, and reports `green` / `red` / `silent` by scanning PRINTED verdict lines, never exit codes. Must FAIL CLOSED (non-zero, with heading/fence diagnostics) when zero blocks are extracted - an anchor corruption once made 41 headings invisible and the gate reported green. |
| groom lint | `accheck <issue-file>`: heading sequence, one fence block per AC, cross-references resolvable, at least 8 level-2 sections. 0 findings required before a groom lands. |
| mirror checker | `mirror-check <n>`: fetches the Platform Issue body and compares it to the LOCAL `_docs/issues/<ID>.md`. It takes one argument (the issue number) and reads the file from a fixed repo path - if pointed at a second copy it silently compares the wrong file. Sync the compared checkout to `origin/main` first. |
| merge gate | `merge.sh <ID> <repo> <branch> "<test command>"`: refuses a dirty main checkout or any untracked file (maintainer exclusions live in `.git/info/exclude`, not the tracked `.gitignore`), fetches the branch, merges `--no-ff`, runs the suite on the MERGED tree, rolls back with `git reset --hard` on failure, pushes, then closes and labels the issue. Worktree cleanup output is cosmetic and may print a fatal while everything else succeeded. |
| worktree helper | `worktree.sh create <ID> -b issue/<ID>-<slug>` with the repo dir and worktree root supplied by environment variables; creates the branch itself. |
| slot ledger | tiny text ledger of in-flight issue ids plus a check that prints `SLOT_FREE n` against the ceiling of 3, merges excluded. Stale ids must be cleared by hand after a lane dies. |
| docs suite gate | validator + issue-ledger anchors + English-only ratchet + fence parity, with a KNOWN-DEBT allowlist where a debt file that turns green while still listed also FAILs, so the ledger cannot rot. Deliberately no `set -o pipefail`: `cmd \| head` SIGPIPEs state-changing commands and has produced false FAILs. |
| DAG readiness | reads `depends:` from each issue's YAML front matter (never the prose body) plus the closed set, prints READY/BLOCKED. |

Machine layout, the part that is not guessable: the repo checkout lives on a Windows-mounted drive
that cannot execute Linux toolchain binaries, so every worktree, `node_modules`, venv and test run
belongs on a native Linux filesystem outside the repo. Worker briefs live INSIDE the worktree as
untracked files (a worker cannot read outside it), which also keeps the main checkout clean for the
merge gate's dirty-tree check. Windows-side helper processes cannot see that Linux filesystem, which
is the whole write-hijack hazard described under Environment traps.
