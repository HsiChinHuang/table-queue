# Coding Standards

All code MUST follow this standard. Violation = Verifier FAIL.

## General Principles

- All code, comments, and documentation MUST be in **English**.
- Use **snake_case** for files, variables, and functions.
- Use **PascalCase** for classes.
- Use **UPPER_SNAKE_CASE** for constants.
- Indentation: 2 spaces (TypeScript / YAML / JSON), 4 spaces (Python).
- Line length: max 100 characters.
- File encoding: UTF-8, no BOM.
- Line endings: LF.

## Python

### Toolchain

| Purpose | Command |
|---|---|
| Install deps | `uv sync` |
| Run tests | `uv run pytest` |
| Lint + fix | `ruff check --fix` |
| Lint JSON | `ruff check --output-format=json` |
| Type check | `uv run mypy .` |

### Naming

- Modules: `snake_case` (`user_model.py`)
- Classes: `PascalCase` (`UserModel`)
- Functions: `snake_case` (`get_user_by_email`)
- Constants: `UPPER_SNAKE_CASE` (`MAX_RETRY_COUNT`)
- Private: prefix `_` (`_internal_helper`)

### Style

- Follow PEP 8.
- Function docstrings in Google style.
- Type annotations MUST be complete.
- Avoid `*args` / `**kwargs` unless necessary.
- Exception handling MUST be specific. `except Exception` is forbidden.

### Testing

- At least 1 test per AC.
- Test file name: `test_<module>.py`.
- Test function name: `test_<action>_<expected>`.
- Group: `class Test<Module>`.
- Assertions MUST be meaningful. `assert True` is forbidden.

## TypeScript

### Toolchain

| Purpose | Command |
|---|---|
| Install deps | `npm install` |
| Compile | `tsc` |
| Run | `tsx <file>` |
| Lint | `eslint .` |
| Type check | `tsc --noEmit` |

### Naming

- Files: `snake_case` (`state_machine.ts`)
- Classes / Interfaces: `PascalCase` (`Handoff`, `IssueState`)
- Functions: `camelCase` (`validateTransition`)
- Constants: `UPPER_SNAKE_CASE` (`MAX_RETRIES`)
- Type aliases: `PascalCase`

### Style

- Use `const` / `let`. `var` is forbidden.
- Prefer arrow functions.
- Use `async` / `await`. Callbacks are forbidden.
- `any` is forbidden. Use `unknown` or explicit types.
- Imports use ES modules.

### Error Handling

- Use `try` / `catch`. Catch MUST handle or re-throw.
- Custom errors MUST extend `Error`.

## YAML

- Indentation: 2 spaces.
- Booleans: `true` / `false` only. `yes` / `no` are forbidden.
- Strings: no quotes unless containing special characters.
- Comments: `#` at start, followed by 1 space.

## JSON

- Indentation: 2 spaces.
- All keys use double quotes.
- Trailing commas are forbidden.
- Comments are forbidden (except `.jsonc`).

## Git

### Commit Message

Use Conventional Commits:

```
<type>(<scope>): <description>

<body>

<footer>
```

Types:

| Type | Purpose |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `test` | Add or modify tests |
| `refactor` | Refactor |
| `docs` | Documentation |
| `chore` | Chores |
| `merge` | Merge |
| `revert` | Revert |

Scope: issue ID, e.g. `t42`.

Example:

```
feat(t42): add signup with invite code

- Add POST /signup endpoint
- Add invite code validation
- Add tests for duplicate email

Closes: t42
```

### Branch

- Naming: `issue/<id>-<slug>`
- Merge conflict fix: `issue/MERGE-FIX-<id>-<slug>`
- Regression fix: `issue/REG-FIX-<id>-<slug>`

### Force Push

Force push to ANY branch is **forbidden**. Detection = BLOCKER.

## Forbidden Actions

| Forbidden | Reason |
|---|---|
| `sudo` / `su` | Privilege escalation |
| `rm -rf /` | System destruction |
| `git push --force` | History rewrite |
| `git push` to main | Bypass process |
| Read `~/.ssh/` | Secret |
| Read `.env` | Secret |
| `env` / `printenv` | Possible leak |
| `curl` / `wget` to non-Platform API | Data exfiltration |
| `dd` / `mkfs` / `fdisk` | Disk operations |
| `chmod 777 /` | Permission destruction |