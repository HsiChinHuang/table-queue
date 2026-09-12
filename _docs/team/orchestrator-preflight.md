# Orchestrator Preflight

Run on every boot, before any issue processing.
Numbers `[key]` resolved from CONFIG_SNAPSHOT.json after Stage 0.

## Stage 0: Config load + validate + snapshot

1. Load `.env` (line-by-line; skip malformed; HALT if all malformed).
2. Load `_docs/config.yaml`; if missing, use `config.yaml.example` defaults.
   Log `[CONFIG_DEFAULT]` if yaml missing.
3. Apply env overrides (only allowed keys; see `_docs/config.md`).
4. Validate all values (type, range, version).
   - Unknown key: warn + log `[CONFIG_UNKNOWN_KEY]`.
   - Near-miss key (edit distance <= 2): HALT.
   - Out-of-range: HALT.
   - On failure: write PREFLIGHT_FAIL.md (file/key/expected/got); HALT.
5. Check `.env` permissions (warn if world-readable).
6. Build redaction dictionary from `API_TOKEN` value.
7. Write `_docs/state/CONFIG_SNAPSHOT.json` (committed).
8. Compare to prior snapshot (if exists):
   - Changed keys -> log `[CONFIG_CHANGED] <key> <old> -> <new>`.
   - Archive prior snapshot to `state/history/config-<ts>.json`.
   - Keep latest `[retention.config_history_keep]`; archive older.

## Stage 1: Environment checks (HALT on failure)

| Check | Command | Expected |
|---|---|---|
| git installed | `git --version` | >= 2.20 |
| in git repo | `git rev-parse --git-dir` | success |
| origin set | `git remote get-url origin` | non-empty |
| state dir writable | `touch _docs/state/.pf && rm _docs/state/.pf` | success |
| log dir writable | `touch _docs/log/.pf && rm _docs/log/.pf` | success |
| issues dir writable | `touch _docs/issues/.pf && rm _docs/issues/.pf` | success |
| worktree base | `mkdir -p ../worktrees` | success |
| platform API ping | GET repo metadata | HTTP 200 |
| `PLATFORM` set | env check | `github` or `gitlab` |
| `API_TOKEN` set | env check | non-empty |
| `REPO_ID` set | env check | non-empty |
| Default branch | `git symbolic-ref refs/remotes/origin/HEAD` | non-empty |
| origin URL | compare to `state/origin-url.txt` | unchanged |
| branch protection | GET API /protection | not protected OR PR-flow configured |

Failure -> write `_docs/state/PREFLIGHT_FAIL.md` (check, reason, UTC ts).
If API available: create BLOCKER issue `label=needs-human`.
HALT.

## Stage 2: Reference integrity scan

Scan all `_docs/**/*.md` for references matching `_docs/...`.

Ignore:
- Dynamic paths: `issues/<ID>.md`, `state/outputs/...`, `log/...`,
  `memory/candidates/...`, `memory/verified/...`.
- Examples: `_docs/*.example`.
- Details files: `_docs/team/details/*`.

For static references: verify **file exists**.
Section references (`Sec. N`) not verified (Markdown has no anchors).
Human review required for section-level correctness.

Missing file -> write `state/PREFLIGHT_FAIL.md`, HALT.

## Stage 3: Project checks (only if `_docs/plan.md` exists)

Read tech-stack from `plan.md`.

| Check | Expected |
|---|---|
| Toolchain present | per tech-stack (uv, npm, etc.) |
| Test runner present | per tech-stack |
| Linter present | per tech-stack |
| Platform labels creatable | API |
| `.gitattributes` | `test -f .gitattributes` present |
| autocrlf uniform | `git config core.autocrlf` = `true` or `input` (same as state) |
| commit.gpgsign | `git config commit.gpgsign` matches repo requirement |
| user.name/email | `git config user.name` / `user.email` both set |

Failure severity:
- Linter missing: log only, do NOT HALT.
- Test runner missing: BLOCKER (SW cannot verify).
- Toolchain missing: BLOCKER (SA/SW cannot proceed).
- `.gitattributes` missing: warn only.
- autocrlf not uniform: HALT.
- GPG mismatch: BLOCKER.
- user.name/email unset: warn only.

## Stage 4: Recovery

See `orchestrator-failures.md` Sec. 6 (Recovery) for:
- Idempotency boundaries.
- WAL-snapshot mismatch.
- Recovery loop counter.
- Slot semantics.

Summary:
1. Load snapshot + log tail + platform.
2. Config change handling:
   - If config changed AND in-flight issues exist:
     - HALT, write PREFLIGHT_FAIL.md.
     - Await human `[CONFIG_CHANGED_OK]` in APPROVALS.md.
   - If config changed AND no in-flight: continue, log `[CONFIG_CHANGED]`.
   - If unchanged: skip.
3. Rebuild state (idempotent).
4. Reconcile map/backlog (see authority doc).
5. Verify no merge/rebase residue (see orchestrator-git.md Sec. 4.3).
   - Check `state/merge-cp.json`.
   - Check `.git/MERGE_HEAD`, `.git/rebase-merge/`.
   - Resume or abort per git.md.
6. Write `[RECOVERY_OK]` or BLOCKER.

## Stage 5: Double-Orchestrator guard

- Check `state/orchestrator.lock`.
- If exists and PID alive -> HALT (another Orchestrator running).
- If exists and PID dead -> overwrite.
- Write own PID + boot UTC ts.

## Stage 6: Pending directory scan

Scan `_docs/issues/pending/*.md`.
For each:
- If Platform has same-title issue -> delete pending file, log `[RECOVERED]`.
- Else -> normal ID assignment flow.

## Stage 7: Heartbeat baseline

- Verify lock exists (created in Stage 5).
- Heartbeat = log's last line UTC timestamp.
- If log stale > `[timeouts.heartbeat_stale_minutes]` min -> considered crashed.

## Degradable features (warn only, do not HALT)

| Feature | If missing |
|---|---|
| memory/ | skip memory reads/writes |
| cache/ | skip caching |
| analysis/ | skip L3/L4 |

## After preflight

If all stages pass: log `[PREFLIGHT_OK]`, proceed to Lifecycle.
Delete `state/PREFLIGHT_FAIL.md` if exists.