# Commands

Commands are defined by `plan.md` tech-stack. Defaults:

## Python

- `uv sync` - install dependencies
- `uv run pytest` - whole suite
- `ruff check --fix` - lint and autofix

## Git (universal)

- `git worktree add ../worktrees/<ID> -b issue/<ID>-<slug>` - create worktree
- `git push -u origin issue/<ID>-<slug>` - push branch
- `git fetch origin` - sync remote
- `git checkout main && git reset --hard origin/main` - sync main
- `git merge --no-ff issue/<ID>-<slug>` - merge branch
- `git worktree remove ../worktrees/<ID>` - cleanup

For non-Python: replace with equivalent in `plan.md`.