# Testing Guidelines

## Commands

Commands are defined by `plan.md` tech-stack. Defaults for Python:
- All tests: `uv run pytest`
- Single file: `uv run pytest tests/test_module.py`
- Single test: `uv run pytest tests/test_module.py::TestClass::test_name -v`
- Linter: `ruff check --fix` (SW, before commit)
- Linter (QA, non-blocking): `ruff check --output-format=json`

If tech-stack is not Python: use the equivalent runner defined in `plan.md`.

## Conventions

- Tests live next to the code they cover, or in `tests/` (per project).
- One test file per module. Name: `test_<module>.py`.
- Group related tests in classes: `Test<Module>`.
- Test names describe behaviour: `test_<action>_<expected>`.

## Rules for QA

- Run the full command listed in `plan.md`, not a subset.
- Report exact command + result count in the verdict.
- If a lint warning appears, log it under `## Lint Report`. Do not fail on lint alone.

## Example layout (Django reference only, not mandatory)

| File | Covers |
|---|---|
| `tests/test_models.py` | Model fields, `__str__`, properties |
| `tests/test_views.py` | HTTP status, redirects, permissions |
| `tests/test_services.py` | Pure business logic, no DB |

When testing template content inside `{% if %}` blocks, check the template source file, not rendered output.