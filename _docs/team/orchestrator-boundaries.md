# Role Boundary Enforcement

Orchestrator enforces role boundaries via pre/post-spawn state diff.

## Snapshot protocol

### Before spawn

Record to `state/boundary-<issue>-<role>.json`:

    {
      "issue_id": "T5",
      "role": "SW",
      "worktree": "../worktrees/T5",
      "branch_sha": "abc123",
      "ac_hash": "sha256:...",
      "constraints_hash": "sha256:...",
      "issues_file_hash": "sha256:...",
      "git_status": ["M file1", "?? file2"],
      "spawn_ts": "2026-09-12T14:00:00Z"
    }

### After spawn

Recompute same fields. Diff.

## Violation classes

| Class | Detection | Severity | Recovery |
|---|---|---|---|
| AC tamper | ac_hash changed, role != PM | BLOCKER | Restore from PM's last write |
| Constraints tamper | constraints_hash changed, role != PM | BLOCKER | Restore from PM's last write |
| Branch tamper | branch_sha changed, role != SW | BLOCKER | Human decides |
| Scope violation | git_status contains paths outside declared scope | BLOCKER | Human decides |
| Secret leak | Output matches secret pattern | BLOCKER | Rotate token, delete comment |
| Forbidden path | Output references forbidden path | WARN | Log only |
| CWD mismatch | Subagent reports wrong pwd | BLOCKER | Re-spawn |

## Secret patterns

### Format patterns

Scan output for:
- `ghp_` + 36 chars (GitHub token).
- `gho_` + 36 chars.
- `ghu_` + 36 chars.
- `ghs_` + 36 chars.
- `glpat-` + 20 chars (GitLab).
- `sk-` + 48 chars (OpenAI).
- `Bearer ` + 20+ chars.
- `-----BEGIN` (PEM).
- Literal `API_TOKEN` value (from CONFIG_SNAPSHOT).

### Whitelist

Skip if:
- Prefix `ghp_test_`, `ghp_example_`, `ghp_fake_`.
- Contains `example`, `placeholder`, `fake`, `dummy`.
- Length < 20 chars.

### Severity

| Match type | Severity | Action |
|---|---|---|
| Literal API_TOKEN value | BLOCKER | Rotate token, delete comment |
| Format match (full) | BLOCKER | Rotate if real; else log |
| Format match (whitelisted) | WARN | Log only |
| Length too short | Ignore | -- |

### On BLOCKER

1. Redact to `[REDACTED]`.
2. Log `[SECRET_LEAK] <issue> <role> <pattern_type>`.
3. Create BLOCKER (without secret).
4. Human rotates token.
5. Remove original comment from platform.

## Forbidden path patterns

- `~/.ssh/`
- `~/.aws/`
- `.env`
- `_docs/state/` (except Orchestrator)
- `_docs/team/orchestrator*.md`
- System paths: `/etc/`, `/var/`, `/usr/`

On match: log `[FORBIDDEN_READ]`. Not BLOCKER unless secret also leaked.

## Scope violation detection

Compare `git status`:
- Allowed: files inside worktree.
- Forbidden: files outside worktree.
- Forbidden: files in `_docs/` (except by PM on own issue file).

On violation:
- List files.
- BLOCKER + needs-human.
- Do NOT auto-revert.

## Worktree cwd check

At spawn, pass absolute worktree path.
Subagent MUST verify as first action:

    pwd == <expected_worktree_path>

If mismatch:
- Post `[BLOCKER] wrong cwd: <actual>`.
- Stop.

## Role-specific boundary rules

| Role | May write | May not write |
|---|---|---|
| SA | plan.md, issues/*, backlog, map | code, state/, other roles |
| PM | issues/<ID>.md (AC/Context/Out-of-scope/DoD) | code, Test req, Impl notes, state/ |
| SW | worktree files, own branch | issues/*.md, state/, other branches |
| QA | (nothing; report only) | code, tests, issues/*.md |
| Orchestrator | state/, log/, labels, backlog, map | issue content, code |

## Enforcement flow

1. On spawn: record snapshot.
2. Subagent runs.
3. Subagent completes.
4. Orchestrator:
   a. Reads latest comment.
   b. Scans for secret/forbidden patterns.
   c. Recomputes state.
   d. Compares snapshot vs current.
   e. Classifies violations.
   f. Acts per recovery matrix.
5. If clean: continue Lifecycle.
6. If violated: BLOCKER, stop related issue.

## Logging

All violations:
`[BOUNDARY] <issue> <role> <class> <detail>`

All recoveries:
`[BOUNDARY_RECOVER] <issue> <class> <action>`