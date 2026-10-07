# Commands

每個 tech-stack 的預設命令。可在 `docs/plan.md` 中覆寫。

## Python（預設）

| 用途 | 命令 |
|---|---|
| 安裝依賴 | `uv sync` |
| 執行所有測試 | `uv run pytest` |
| 執行單一檔案 | `uv run pytest tests/test_<name>.py` |
| 執行單一測試 | `uv run pytest tests/test_<name>.py::<Class>::<test> -v` |
| Lint + fix | `ruff check --fix` |
| Lint JSON | `ruff check --output-format=json` |

## Node.js

| 用途 | 命令 |
|---|---|
| 安裝依賴 | `npm install` |
| 執行所有測試 | `npm test` |
| Lint + fix | `npm run lint -- --fix` |

## Git（通用）

| 用途 | 命令 |
|---|---|
| 建立 worktree | `git worktree add ../worktrees/<id> -b issue/<id>-<slug>` |
| 推送分支 | `git push -u origin issue/<id>-<slug>` |
| 同步遠端 | `git fetch origin` |
| 同步 main | `git checkout main && git reset --hard origin/main` |
| 合併分支 | `git merge --no-ff issue/<id>-<slug>` |
| 移除 worktree | `git worktree remove ../worktrees/<id>` |

## Platform API

All Platform (GitHub / GitLab) operations go through a single CLI:
`npx tsx scripts/platform.ts <resource> <action> [options]`. The CLI reads
`.env` (`PLATFORM`, `API_TOKEN`, `REPO_ID`) and outputs JSON to stdout.

**Do NOT** call the Platform API directly from skills; always use this
CLI so that auth, REPO_ID normalization, and platform differences are
handled in one place.

### Issue

| 用途 | 命令 |
|---|---|
| Create issue | `npx tsx scripts/platform.ts issue create --title "<t>" --body "<b>" --labels "l1,l2"` |
| Get issue | `npx tsx scripts/platform.ts issue get <number>` |
| Close issue | `npx tsx scripts/platform.ts issue close <number>` |
| Reopen issue | `npx tsx scripts/platform.ts issue reopen <number>` |
| Post comment | `npx tsx scripts/platform.ts issue comment <number> --body "<b>"` |
| Read latest comment | `npx tsx scripts/platform.ts issue latest-comment <number>` |
| List issues | `npx tsx scripts/platform.ts issue list [--labels "l1,l2"] [--state open\|closed\|all]` |

### Label

| 用途 | 命令 |
|---|---|
| Add labels | `npx tsx scripts/platform.ts label add <number> --labels "l1,l2"` |
| Remove one label | `npx tsx scripts/platform.ts label remove <number> --label "l"` |
| Replace all labels | `npx tsx scripts/platform.ts label set <number> --labels "l1,l2"` |

### Output

Every command prints a JSON document to stdout:

```json
{
  "number": 42,
  "title": "...",
  "state": "open",
  "labels": ["defined"],
  "updated_at": "2026-10-07T09:33:18Z"
}
```

`issue list` prints a JSON array. `issue latest-comment` prints a comment
object or `null` (when the issue has no comments). `issue comment` prints
the created comment.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Runtime error (HTTP non-2xx, network failure, invalid config) |
| 2 | Usage error (bad arguments) |

### REPO_ID normalization

`REPO_ID` in `.env` accepts any of:

```
owner/repo
https://github.com/owner/repo
https://github.com/owner/repo.git
git@github.com:owner/repo.git
```

All four normalize to `{owner, repo}`. `PLATFORM=gitlab` uses the same
formats with a GitLab host.

## Git Credentials

`git push` MUST NOT trigger an interactive credential prompt. The Launcher
injects two environment variables into the Orchestrator subprocess before
spawning it:

- `GIT_ASKPASS` — points to `scripts/git_askpass.sh` (Unix) or
  `scripts/git_askpass.cmd` (Windows). The helper responds with the
  `API_TOKEN` from `.env` when git asks for the password.
- `GIT_TERMINAL_PROMPT=0` — disables git's fallback terminal prompt, so
  missing credentials fail fast instead of opening a browser or TTY.

These variables propagate to every subagent (Builder, Verifier) that the
Orchestrator spawns, so no subagent has to set them.

**Do NOT** edit `GIT_ASKPASS` or `GIT_TERMINAL_PROMPT` in `.env`; the
Launcher sets them programmatically. If you need custom credential
handling, edit `launcher/index.ts` (`resolveGitAskpassPath`).

## Shared venv (Python read-only phases)

Builder always uses a per-worktree `.venv` (it may modify dependencies).

Verifier uses a hash-bucketed shared venv to avoid per-worktree installs.
The bucket hash is `sha256(pyproject.toml || uv.lock)[:16]`, so worktrees
with identical dependency specifications share the same venv while
different specifications get isolated buckets.

**The Orchestrator prepares the shared venv and injects environment
variables before spawning a Verifier. Verifier command strings are
NOT modified**; `uv run pytest` and similar resolve to the shared venv
automatically via:

- `UV_PROJECT_ENVIRONMENT` — the shared venv path
- `PYTHONPATH` — the current worktree path (so the local code takes
  precedence over any stale editable install)

### Lifecycle

1. Orchestrator runs `python scripts/venv_path.py --root <worktree>` before
   the first Verifier spawn for a given dependency hash.
2. If the path does not exist, Orchestrator runs
   `python scripts/venv_path.py --root <worktree> --create`
   (1–3 minutes; runs in the Orchestrator's own time, not inside a slot).
3. Orchestrator spawns the Verifier with `UV_PROJECT_ENVIRONMENT` and
   `PYTHONPATH` set to the resolved values.

### Fallback

If `pyproject.toml` or `uv.lock` is missing in the worktree,
`scripts/venv_path.py` exits with code 1. The Orchestrator logs
`[VENV_UNAVAILABLE]` and the Verifier falls back to per-worktree
`uv sync`.

### Cleanup

`scripts/venv_cleanup.py --root .` lists buckets older than 30 days.
Re-run with `--delete` to remove them. No automatic cleanup is performed.

## 非 Python

在 `docs/plan.md` 的 tech-stack 區塊定義對應命令。