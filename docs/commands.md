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

## 非 Python

在 `docs/plan.md` 的 tech-stack 區塊定義對應命令。