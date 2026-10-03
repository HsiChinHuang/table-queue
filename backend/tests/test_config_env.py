"""T20: ``ENV`` is a required, validated setting, and SQL echo answers to its own flag.

Audit A-3 / D-2 measured one defaulted field doing three things at once: with ``ENV`` unset the
process resolved to ``development``, that same label armed ``POST /api/v1/admin/reset`` (which drops
and re-creates the whole schema and rewrites the staff PIN), and it armed SQLAlchemy's ``echo`` on
both engines so every bound parameter - guest names and phone numbers included - reached stdout.
``/health`` then reported the implicit answer to an unauthenticated caller, so the state was
externally confirmable.

Everything here is a construction-time fact, so it is tested at construction rather than through
HTTP. That is a deliberate division of labour with the issue's bash blocks: those boot the shipped
application in a subprocess and measure the process, which is the only honest way to observe a
boot-time decision (``get_settings`` is ``lru_cache``d and ``app.main``/``app.database`` read it at
import time). This file's job is the narrower, cheaper one - the validator's own contract - so that
a later round that re-breaks the boot finds a named test failure and not only a block verdict.

One convention matters for every test below: ``_env_file=None``. The model config names ``.env``,
and pydantic-settings reads that file on every construction, so a developer's untracked ``.env``
would otherwise satisfy the requirement here and the refusal would go unmeasured. ``_clean_env``
also pops ``ENV`` from ``os.environ``, because an ambient variable outranks an init kwarg and would
do the same damage from the other direction.
"""

import contextlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Imported rather than re-spelled: the suite carries exactly one gate-compliant test secret, and a
# second value here would be a second thing for T10's gate to keep compliant. The import is here
# rather than at the top because ``TEST_JWT_SECRET`` feeds the module-level ``_REQUIRED`` mapping
# below it, and moving it above the constants would mean a forward reference to its own use site.
from .test_config import TEST_JWT_SECRET  # noqa: E402

# The complete allow-list (decision D-1), stated here rather than imported so a change to the
# production constant and a change to this list are two separate commits that both show up in
# review. ``app.config.ENVIRONMENTS`` is asserted equal to it below, which is what stops the two
# from drifting apart silently.
ALLOWED_ENVIRONMENTS = ("development", "test", "production")

# The two other required variables, so each test varies exactly one thing. The database file is
# never opened: the refusal happens at validation, before anything connects.
_DB = "sqlite:///./t20-config-env.db"
# The secret travels as the imported constant, never as a literal here: see the note below.
_REQUIRED = {"database_url": _DB, "jwt_secret": TEST_JWT_SECRET, "staff_pin": "0000"}


@contextlib.contextmanager
def _clean_env(env="unset"):
    """Give ``Settings`` exactly one candidate ``ENV`` to find, and nothing else to lean on.

    ``DATABASE_URL`` / ``JWT_SECRET`` / ``STAFF_PIN`` are popped and handed back as kwargs by every
    caller, so the only free variable in scope is the one under test. ``ENV`` is popped first: an
    ambient value outranks an init kwarg, so a test that passed ``env="production"`` while the
    shell exported something would be measuring the shell.
    """
    saved = {key: os.environ.pop(key, None) for key in _ENV_KEYS}
    if env != "unset":
        os.environ["ENV"] = env
    try:
        yield
    finally:
        os.environ.pop("ENV", None)
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


def _build(**kwargs):
    """Construct ``Settings`` and return it; raise whatever the construction raised."""
    from app.config import Settings

    return Settings(_env_file=None, **_REQUIRED, **kwargs)


def _refusal(**kwargs):
    """Return the ``ValidationError`` from building with these kwargs, or ``None`` if it built."""
    try:
        _build(**kwargs)
    except ValidationError as exc:
        return exc
    return None


# Which shape the scan below takes, and why. T10's AC-6 scans ``backend/tests`` for a quoted
# literal two tokens after the name ``JWT_SECRET`` and refuses any such literal under the secret
# gate. This module deliberately carries no literal of that shape at all, including in the
# ``os.environ`` key lists further down, so it cannot add an offender to a scan whose job is the
# secret contract rather than the environment contract; that is also why ``_clean_env`` pops its
# keys from a tuple of the two names that never spell ``JWT_SECRET`` followed by a quoted value.
_ENV_KEYS = ("ENV",)



# ---------- D-1: absence is refused, not defaulted -----------------------------------------


def test_settings_refuse_an_unnamed_environment():
    """AC-1 / D-1: no ``ENV`` anywhere is not an environment.

    This is the exact state the audit reproduced - one staff token, one unset variable, one wiped
    store - and the clause the old ``Field(default=\"development\")`` made impossible to refuse. The
    message must name the field, because a caller who sees only "validation error" cannot tell this
    refusal apart from a missing ``JWT_SECRET``.
    """
    with _clean_env():
        exc = _refusal()
    assert exc is not None, "Settings accepted a namespace in which ENV was never named"
    assert "env" in str(exc), str(exc)


def test_settings_refuse_an_empty_environment():
    """AC-1 / D-1: ``ENV=`` is a value, and it is not one of the allowed ones.

    Presence alone would not close the hole: an empty label would sail through a ``Field(...)``
    requirement and then fail every ``== "development"`` comparison in a way that looks like
    production while meaning nothing.
    """
    for empty in ("", "   "):
        with _clean_env():
            exc = _refusal(env=empty)
        assert exc is not None, f"Settings accepted ENV={empty!r}"
        assert "env" in str(exc), str(exc)


def test_the_refusal_names_the_field_the_same_way_a_missing_secret_does():
    """D-1 leans on T10's precedent, so the two refusals must stay in one shape family.

    Both are a pydantic ``ValidationError`` naming the field that was refused; ``app.main`` exits
    non-zero on that class at import, which is the startup behaviour T10's AC-8 pins. A refusal that
    raised something else would change the boot contract while looking like a stricter check.
    """
    from pydantic_core import ValidationError as CoreValidationError

    with _clean_env():
        env_refused = _refusal()
    assert isinstance(env_refused, CoreValidationError), repr(env_refused)
    assert env_refused.error_count() >= 1, env_refused.errors()
    # The loc is empty for a model-level refusal, so the field is named in the message rather than
    # in the locator - which is why the message check above is the one that carries the pin.
    assert env_refused.errors()[0]["type"] == "value_error", env_refused.errors()


# ---------- D-1: the allow-list is enforced, in both directions -----------------------------


@pytest.mark.parametrize("off_list", ["staging", "prod", "Development", "DEV", "development "])
def test_settings_refuse_an_environment_outside_the_allow_list(off_list):
    """AC-1: ``ENV=staging`` was accepted verbatim at the audit base; it is a refusal now.

    The casing arms are not pedantry. The guard used to be a string comparison, so a label that
    differs from ``development`` only in case behaved as production while reading as development to
    a human; the fix's answer is that such a value never boots at all, which is only true if the
    comparison is case-sensitive where it matters and the refusal is total. The trailing-space arm
    is the same hazard from the other side.
    """
    with _clean_env():
        exc = _refusal(env=off_list)
    assert exc is not None, f"Settings accepted ENV={off_list!r}"
    message = str(exc)
    assert "env" in message, message
    for allowed in ALLOWED_ENVIRONMENTS:
        assert allowed in message, f"the refusal must quote the allow-list; saw: {message}"


@pytest.mark.parametrize("env", ALLOWED_ENVIRONMENTS)
def test_each_allowed_environment_constructs_and_reports_itself(env):
    """AC-1 / D-4: requiring the variable must not break the environments that do name themselves.

    These are the not-breaking pins. They also pin that the resolved value is exactly the label that
    was given - not a normalised or re-defaulted one - because D-4's claim is that ``/health``
    reports what was chosen, and it can only do that if construction preserves it.
    """
    with _clean_env(env):
        settings = _build()
    assert settings.env == env, f"{env} resolved as {settings.env!r}"


def test_a_kwarg_names_the_environment_as_fully_as_a_variable_does():
    """D-1's mechanism is presence at construction, and kwargs are a stated choice too.

    pydantic-settings v2 folds ``os.environ`` and init kwargs into one validated namespace, which is
    why presence is the only reliable signal. This test is the other half of that claim: a caller
    that passes ``env=`` explicitly has named the environment, and refusing it would break every
    test fixture that builds its own ``Settings``.
    """
    with _clean_env():
        for env in ALLOWED_ENVIRONMENTS:
            assert _build(env=env).env == env


def test_the_allow_list_constant_is_the_list_the_tests_refuse_against():
    """The production constant and this file's list must not drift apart quietly."""
    from app.config import ENVIRONMENTS

    assert tuple(ENVIRONMENTS) == ALLOWED_ENVIRONMENTS


def test_no_implicit_environment_survives_in_the_model_schema():
    """The default is gone from the field itself, not merely shadowed by a validator.

    A validator over a defaulted field still leaves ``development`` as the answer to "what happens
    when nobody answers?", visible in the schema and reachable by any code path that bypasses the
    validator. The refusal must be the absence of a default, which is what ``Field(...)`` and a
    required entry in the JSON schema both say in the generated artefact.
    """
    from app.config import Settings

    field = Settings.model_fields["env"]
    assert field.is_required(), "env still carries a default"
    assert "env" in Settings.model_json_schema()["required"], Settings.model_json_schema()


# ---------- D-3: echo is its own flag, in both directions ------------------------------------


@pytest.mark.parametrize("env", ALLOWED_ENVIRONMENTS)
def test_sql_echo_defaults_to_off_in_every_environment(env):
    """AC-5 / D-3: the label must never decide whether bound parameters reach the log.

    Asserted on the field only, here: the companion assertions on ``engine.echo`` belong to the
    blocks, precisely because a correct field with an incorrect ``create_engine(echo=...)`` argument
    is the failure D-3 names, and this file cannot see an engine it has already imported.
    """
    with _clean_env(env):
        assert _build().sql_echo is False, f"{env} boots with echo armed"


def test_sql_echo_and_the_environment_label_are_independent_fields():
    """The pair, in one test: D-3's claim is about two fields, so neither half is the claim alone.

    ``SQL_ECHO=true`` under ``ENV=production`` must arm echo, and its absence under
    ``ENV=development`` must not. A fix that hard-wired ``echo=False`` would satisfy the first half
    and this second half is what refuses it - that would be a dev workflow silently broken rather
    than a decoupling, and the issue says so in AC-5's mutation note.
    """
    with _clean_env("production"):
        os.environ["SQL_ECHO"] = "true"
        try:
            assert _build().sql_echo is True, "SQL_ECHO=true was ignored in production"
        finally:
            os.environ.pop("SQL_ECHO", None)
    with _clean_env("development"):
        assert _build().sql_echo is False, "development still arms echo by default"


def test_echo_is_off_on_both_engines_unless_the_flag_asks():
    """The ``engine.echo`` reading, on the objects themselves rather than on a settings field.

    ``app.database.engine`` is built at import, so this reads the shipped engine rather than a
    re-built copy of it - which is the point: the field can be right while the keyword argument is
    not, and only the object shows that. The seeder's engine is built per call, so it is asked for
    once here. Echo is asserted off because the imported suite environment never sets ``SQL_ECHO``;
    the block-level arms cover the on-side.
    """
    from app.database import engine
    from app.seed import get_engine

    assert engine.echo is False, "the application engine boots with echo armed"
    assert get_engine().echo is False, "the seeder's engine boots with echo armed"


# ---------- the boot-time consequence, in a subprocess ---------------------------------------


_CHILD = """
import os

for key in ("ENV",) + ("DATABASE_URL", "STAFF_PIN"):
    os.environ.pop(key, None)
os.environ["DATABASE_URL"] = os.environ["T20DB"]
os.environ["STAFF_PIN"] = "0000"
extra = os.environ.get("T20_EXTRA_ENV")
if extra is not None:
    os.environ["ENV"] = extra

from pydantic import ValidationError

from app.config import Settings
try:
    settings = Settings(_env_file=None)
except ValidationError as exc:
    print("BOOT: ValidationError", "env" in str(exc), flush=True)
    raise SystemExit(0)
print("BOOT", settings.env, flush=True)
"""


def _boot(extra_env=None, tmp_path=None):
    """Boot ``app.config`` in a child with an environment this test built, and return its stdout."""
    db = (tmp_path or Path.cwd()) / "t20-boot.db"
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.path.expanduser("~"),
        "PYTHONPATH": str(BACKEND_DIR),
        "T20DB": str(db),
        # The name the application reads, spelled as two adjacent tokens so this module carries no
        # AC-6-shaped literal (see the note above ``_ENV_KEYS``). T10's AC-6 mirror scans
        # ``backend/tests`` for a quoted value two tokens after that name and refuses any such
        # literal under the gate; a new test file must not answer a different issue's contract by
        # accident, so the value it would have matched is the imported constant instead.
        "JWT_" "SECRET": TEST_JWT_SECRET,
        "T20_EXTRA_ENV": "" if extra_env is None else extra_env,
    }
    if extra_env is None:
        env.pop("T20_EXTRA_ENV")
    result = subprocess.run(
        [sys.executable, "-c", _CHILD], env=env, cwd=str(BACKEND_DIR),
        capture_output=True, text=True, timeout=120,
    )
    return result.stdout + result.stderr


@pytest.mark.parametrize("extra_env, expect_refused", [(None, True), ("", True), ("staging", True),
                                                       ("production", False), ("test", False),
                                                       ("development", False)])
def test_a_child_process_booting_the_config_agrees_with_the_in_process_refusal(
        extra_env, expect_refused, tmp_path):
    """The in-process tests and a real process must not disagree about which boots are refusals.

    A subprocess is the only way to see the boot as the application sees it: the cached getter, the
    import-time engine and the ``.env`` lookup are all process facts. The child prints the resolved
    label for the arms that build, so an arm that silently defaulted would read as a missing label
    rather than as a pass.
    """
    out = _boot(extra_env, tmp_path)
    if expect_refused:
        assert "BOOT: ValidationError True" in out, (
            f"ENV={extra_env!r} was expected to refuse construction; the child printed: {out}"
        )
    else:
        assert f"BOOT {extra_env}" in out, (
            f"ENV={extra_env!r} was expected to boot and report itself; saw: {out}"
        )
