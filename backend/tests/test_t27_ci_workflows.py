"""t27: the CI and audit workflow files exist, parse as YAML, and carry the required coverage.

The platform-side green (ac5) is not testable here; everything the ACs require of the
files themselves is: presence, YAML validity, triggers, job coverage, the Node 20 pin,
the pip-audit dev dependency, the README documentation, and the absence of secret
material (ac4's grep, mirrored here so a regression is caught by the suite).
"""

import re
import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

SECRET_PATTERN = re.compile(
    r"ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|BEGIN [A-Z ]*PRIVATE KEY|JWT_SECRET\s*[:=]|STAFF_PIN\s*[:=]|api[_-]?key",
    re.IGNORECASE,
)


def _load(name: str) -> dict:
    path = WORKFLOWS / name
    assert path.is_file(), f"missing workflow file: {path}"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(doc, dict), f"{name} did not parse to a mapping"
    return doc


def _on(doc: dict) -> dict:
    # YAML 1.1 (PyYAML) parses the bare `on` key as boolean True.
    on = doc.get("on", doc.get(True))
    assert isinstance(on, dict), "workflow has no trigger mapping"
    return on


def _job_texts(doc: dict) -> list[str]:
    """Job-level env keys plus every step name/run/uses string, for coverage greps."""
    texts = []
    jobs = doc.get("jobs")
    assert isinstance(jobs, dict) and jobs, "workflow defines no jobs"
    for job in jobs.values():
        for key in job.get("env") or {}:
            texts.append(str(key))
        for step in job.get("steps", []):
            for key in ("name", "run", "uses"):
                if step.get(key):
                    texts.append(str(step[key]))
    return texts


def test_ci_workflow_exists_parses_and_triggers_on_push():
    doc = _load("ci.yml")
    assert "push" in _on(doc), "ci.yml must trigger on push"


def test_ci_workflow_covers_backend_ruff_and_pytest_under_two_pinned_tz():
    doc = _load("ci.yml")
    joined = "\n".join(_job_texts(doc))
    assert "ruff" in joined, "no ruff check step in ci.yml"
    assert "pytest" in joined, "no pytest step in ci.yml"
    tz_matrix = None
    for job in doc["jobs"].values():
        matrix = (job.get("strategy") or {}).get("matrix") or {}
        if "tz" in matrix:
            tz_matrix = matrix["tz"]
    assert tz_matrix == ["UTC", "Asia/Taipei"], (
        f"pytest job must run under exactly the two pinned clocks, got {tz_matrix!r}"
    )
    assert "TZ" in joined, "the pinned clock must be exported as TZ"


def test_ci_workflow_covers_frontend_tsc_eslint_vitest_and_build_smoke():
    doc = _load("ci.yml")
    joined = "\n".join(_job_texts(doc))
    assert "tsc" in joined, "no tsc --noEmit step in ci.yml"
    assert "eslint" in joined, "no eslint step in ci.yml"
    assert "vitest" in joined, "no vitest step in ci.yml"
    assert "npm run build" in joined, "no build smoke (npm run build) step in ci.yml"
    node_pins = [
        step.get("with", {})
        for step in (s for job in doc["jobs"].values() for s in job.get("steps", []))
        if str(step.get("uses", "")).startswith("actions/setup-node")
    ]
    assert node_pins, "no actions/setup-node step in ci.yml"
    for withs in node_pins:
        if "node-version-file" in withs:
            assert withs["node-version-file"] == ".nvmrc"
        else:
            assert str(withs.get("node-version", "")) == "20", (
                f"setup-node must pin Node 20, got {withs!r}"
            )


def test_nvmrc_pins_node_20():
    nvmrc = REPO_ROOT / ".nvmrc"
    assert nvmrc.is_file(), "missing .nvmrc"
    lines = [line for line in nvmrc.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines == ["20"], f".nvmrc must contain exactly '20', got {lines!r}"


def test_audit_workflow_exists_parses_and_triggers_on_pull_request():
    doc = _load("audit.yml")
    assert "pull_request" in _on(doc), "audit.yml must trigger on pull_request"


def test_audit_workflow_covers_npm_audit_pip_audit_and_gitleaks():
    doc = _load("audit.yml")
    joined = "\n".join(_job_texts(doc))
    assert "npm audit" in joined, "no npm audit step in audit.yml"
    assert "pip-audit" in joined, "no pip-audit step in audit.yml"
    assert "gitleaks" in joined, "no gitleaks secret scan in audit.yml"


def test_workflow_files_contain_no_secret_material():
    for name in ("ci.yml", "audit.yml"):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        match = SECRET_PATTERN.search(text)
        assert match is None, f"{name} contains secret material: {match.group(0)!r}"


def test_pip_audit_is_in_backend_dev_group_and_documented_in_readme():
    pyproject_path = REPO_ROOT / "backend" / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    dev = pyproject.get("dependency-groups", {}).get("dev", [])
    assert any(dep.startswith("pip-audit") for dep in dev), (
        f"pip-audit missing from backend dev group: {dev!r}"
    )
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "pip-audit" in readme.lower(), "README dev section does not document pip-audit"
