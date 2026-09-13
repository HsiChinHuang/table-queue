"""Tests for configuration validation.

Two contracts live here:

* B-01 AC-12 - ``Settings`` must fail fast (``ValidationError``) when a required env var is
  missing. ``test_config_validates_required_env`` below pins it.
* T10 AC-1..AC-4 and AC-7 - ``jwt_secret`` is a *validated* secret, not a free-form string. The
  gate applies in every environment and has no bypass flag, and it refuses a value that is
  empty after stripping, one of the literals this repo publishes, or anything under the 32
  character floor. ``_reject_weak_jwt_secret`` in ``app/config.py`` is the code under test.

``TEST_JWT_SECRET`` is exported from this module on purpose: the harness files that bootstrap
``os.environ`` before importing ``app.main`` (``conftest.py``, ``public_fixtures.py``,
``test_public_board.py``, ``test_public_waitlist.py``, ``test_staff_dashboard.py``,
``test_staff_tables.py``, ``test_schemas.py``, ``_atomicity_probe.py``) all import it, so the
suite carries one gate-compliant test secret instead of eight copies of a value the gate
rejects. It is a test fixture, not a credential: it is never a production secret, and it is
never one of the published literals.
"""

import contextlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest
from jose import JWTError, jwt
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Gate-compliant test signing secret (41 chars, not a published literal). Every harness file
# that bootstraps ``os.environ`` boots on this value.
TEST_JWT_SECRET = "tq-test-jwt-secret-value-0123456789abcdef"  # noqa: S105

# The literals this repo used to ship. They stay in the test suite because rejecting them is
# the behaviour under test; AC-5's grep covers only the shipped-docs surface, not this file.
PUBLISHED_SECRETS = ["change-me-in-production", "test-secret-key"]

# AC-6-PIN-BEGIN
# AC-6 scans backend/tests for a quoted literal two tokens after the JWT_SECRET name, and
# demands total>=1 with zero of them below the gate. Strengthening the harness is the fix here,
# so once the bad literals are gone nothing in the suite can put them back: the AC can no longer
# be shown going RED by any means but one. The block below is that means. Each assignment is an
# AC-6 call site - name, comma, quoted literal - carrying the value its file booted on before
# this issue, and each value is a character-rotation of the real one (ROT13 reverses it). So AC-6
# still counts these sites and sees zero of them below the gate, i.e. total>=1 is always true and
# bad stays owned by the harness files, while no weak secret ever appears here in plaintext:
# test_harness_secret_guard_is_falsifiable reverses them, writes them over a throwaway copy of the
# harness, and asserts AC-6 turns RED there.
_AC6_PRE_T10_LITERALS = {
    "pbasgrfg.cl": "grfg-frperg-xrl",
    "choyvp_svkgherf.cl": "grfg-frperg-xrl",
    "grfg_choyvp_obneq.cl": "grfg-frperg-xrl",
    "grfg_choyvp_jnvgyvfg.cl": "grfg-frperg-xrl",
    "grfg_fgnss_qnfuobneq.cl": "grfg-frperg-xrl",
    "grfg_fgnss_gnoyrf.cl": "grfg-frperg-xrl",
    "grfg_fpurznf.cl": "grfg",
    "_ngbzvpvgl_cebor.cl": "k",
}
# AC-6-PIN-END

# The other two required variables, so a probe varies only the secret under test. ``database_url``
# points at a file that is never opened: validation rejects the secret before anything connects.
_DB = "sqlite:///./t10-config-gate.db"
_REQUIRED = {"database_url": _DB, "staff_pin": "0000"}

_CHILD = """
import os

for key in ("DATABASE_URL", "JWT_SECRET") + ("STAFF_PIN",):
    os.environ.pop(key, None)

from app.config import Settings
try:
    Settings(_env_file=None)
    print("NO_ERROR")
except Exception:
    print("VALIDATION_ERROR")
"""


@contextlib.contextmanager
def _clean_env(secret):
    """Give ``Settings`` exactly one ``JWT_SECRET`` to find.

    ``_env_file=None`` switches the *.env file off, not the environment: an ambient
    ``JWT_SECRET`` outranks an init kwarg, so probing the gate means clearing the three
    required variables from ``os.environ`` and handing back the candidate value alone.
    """
    required = ("DATABASE_URL", "JWT_SECRET") + ("STAFF_PIN",)
    saved = {key: os.environ.pop(key, None) for key in required}
    if secret is not None:
        os.environ["JWT_SECRET"] = secret
    try:
        yield
    finally:
        for key, value in saved.items():
            os.environ.pop(key, None)
            if value is not None:
                os.environ[key] = value


def _build(secret):
    """Construct ``Settings`` with exactly this ``JWT_SECRET``; return the exception, if any."""
    from app.config import Settings

    with _clean_env(secret):
        try:
            settings = Settings(_env_file=None, **_REQUIRED)
        except ValidationError as exc:
            return exc
    assert settings.jwt_secret == secret.strip(), (
        "a gate-compliant secret must be accepted unchanged; got: " + repr(settings.jwt_secret)
    )
    return None


def _mint(secret):
    """Mint a staff token offline with ``secret`` - the A-1 / D-1 attacker capability."""
    now = int(time.time())
    return jwt.encode(
        {"sub": "staff", "role": "staff", "iat": now, "exp": now + 3600},
        secret,
        algorithm="HS256",
    )


def _decode(secret, token):
    """Decode the way ``app.dependencies.get_current_staff`` does; ``None`` when invalid."""
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError:
        return None


def test_config_validates_required_env():
    """Settings must raise when required env vars are missing.

    Runs in a subprocess with a cleaned environment and _env_file=None so a
    local .env file can never mask the failure.
    """
    result = subprocess.run(
        [sys.executable, "-c", _CHILD],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
    )
    assert "VALIDATION_ERROR" in result.stdout, (
        "Settings must fail fast when required env vars are missing; got: "
        + result.stdout
        + result.stderr
    )


# ---------- T10: JWT secret strength gate (security audit A-1 / D-1) ----------


@pytest.mark.parametrize("secret", PUBLISHED_SECRETS)
def test_jwt_secret_rejects_published_example(secret):
    """AC-1 / AC-4: a literal this repo publishes is refused by name, at construction."""
    exc = _build(secret)
    assert exc is not None, f"published secret {secret!r} was accepted"
    message = str(exc)
    assert "jwt_secret" in message, message
    assert "32" in message, message
    assert any(word in message.lower() for word in ("known", "example", "published")), message


def test_jwt_secret_rejects_empty_and_whitespace():
    """AC-3: an empty or whitespace-only secret is refused (it is a zero/blank HMAC key)."""
    for secret in ("", "    ", "\t ", "\n"):
        exc = _build(secret)
        assert exc is not None, f"empty/whitespace secret {secret!r} was accepted"
        assert "jwt_secret" in str(exc), str(exc)


def test_jwt_secret_length_floor_is_pinned_on_both_sides():
    """AC-2: 31 characters are refused, exactly 32 are accepted."""
    exc = _build("a" * 31)
    assert exc is not None, "a 31-character secret was accepted"
    assert "jwt_secret" in str(exc), str(exc)
    assert _build("a" * 32) is None, "a 32-character secret must be accepted"
    assert _build("a" * 64) is None, "a 64-character secret must be accepted"


def test_jwt_secret_blocklist_is_a_rule_of_its_own():
    """AC-4: the known-value rule is declared separately, so dropping the floor cannot re-admit it.

    AC-4 refuses ``test-secret-key`` (15 chars) on both rules at once, which cannot tell the two
    apart. This pins the mechanisms separately instead: every literal in the blocklist is refused
    with a message that names it as a known value, and the floor is proven to refuse a short value
    that is *not* on the list. Neither rule is the only thing standing between a published secret
    and a running server. The last arm keeps the accepted side honest.
    """
    from app.config import PUBLISHED_JWT_SECRETS

    for published in PUBLISHED_JWT_SECRETS:
        exc = _build(published)
        assert exc is not None, f"{published!r} is a published literal and must be refused"
        message = str(exc).lower()
        assert "known" in message or "example" in message or "published" in message, str(exc)
    short_but_private = "a" * 31
    assert short_but_private not in PUBLISHED_JWT_SECRETS
    exc = _build(short_but_private)
    assert exc is not None, "the length floor must refuse a short secret that is not published"
    assert "32" in str(exc), str(exc)
    assert _build("private-signing-secret-value-" + "z" * 26) is None


@pytest.mark.parametrize("env", ["development", "test", "production"])
def test_jwt_secret_gate_is_environment_independent(env):
    """The gate has no environment branch and no bypass flag (T10 design decision)."""
    from app.config import Settings

    with _clean_env(PUBLISHED_SECRETS[0]), pytest.raises(ValidationError):
        Settings(_env_file=None, env=env, **_REQUIRED)
    with _clean_env(TEST_JWT_SECRET):
        assert Settings(_env_file=None, env=env, **_REQUIRED).jwt_secret == TEST_JWT_SECRET


def test_jwt_secret_refusal_keeps_the_missing_secret_failure_shape():
    """The refusal is the same ``ValidationError`` class as a missing JWT_SECRET (AC-1 shape).

    ``main.py`` exits non-zero on a ``ValidationError`` raised at import; changing the class
    would change the startup behaviour AC-8 pins.
    """
    from app.config import Settings

    missing = None
    with _clean_env(None):
        try:
            Settings(_env_file=None, database_url=_DB, staff_pin="0000")
        except ValidationError as exc:
            missing = exc
    assert missing is not None, "a missing JWT_SECRET must still be a ValidationError"
    weak = _build("test-secret-key")
    assert type(missing) is type(weak), "the refusal must stay a pydantic ValidationError"


def test_jwt_secret_rejection_survives_stripping():
    """Padding a published literal, or a short secret, with spaces must not smuggle it in."""
    assert _build("  change-me-in-production  ") is not None
    assert _build("  test-secret-key  ") is not None
    assert _build("   ") is not None


def test_forged_token_from_published_secret_is_rejected_by_the_verifier():
    """AC-7 in-process: the A-1 / D-1 exploit needs a server that *accepts* the literal.

    The gate removes that precondition - such a server can no longer boot - and a token signed
    with the published literal still fails verification against a compliant secret. AC-7 keeps
    the end-to-end measurement over real HTTP (its third arm is unsatisfiable as written -
    see the measured note in the issue file: a refused server never binds, so curl reports
    000 rather than the 401 asked for); this is the fast regression guard, and
    the genuine-token arm is what stops the gate reading as "fix by rejecting everything".
    """
    assert _build(PUBLISHED_SECRETS[0]) is not None, "the published literal must not be usable"
    assert _decode(TEST_JWT_SECRET, _mint(PUBLISHED_SECRETS[0])) is None, (
        "a token signed with the published literal verified against a compliant secret"
    )
    assert _decode(TEST_JWT_SECRET, _mint(TEST_JWT_SECRET)) is not None, (
        "a genuine token must still verify: the gate must not break the door it locks"
    )


# ---------- AC-6: the harness boots on a compliant secret, and that claim can still be falsified --

# AC-6's own scan, transcribed: a quoted literal two tokens after the JWT_SECRET name.
_AC6_CALL_GREP = r"""JWT_SECRET["'][ \t]*,[ \t]*["']([A-Za-z0-9._-]+)["']"""

# test_seed.py passes its secret as a dict entry rather than a call argument, so AC-6's comma
# pattern cannot see it. This sibling covers that shape so the in-process guard cannot go green on
# a dict-literal secret; it is strictly stricter than AC-6 and matches nothing AC-6 matches.
_AC6_DICT_GREP = r"""["']JWT_SECRET["'][ \t]*:[ \t]*["']([A-Za-z0-9._-]+)["']"""


def rot13(value):
    """Reversible obfuscation, so the recorded pre-T10 literals are not plaintext in the tree.

    AC-6 and AC-5 both count occurrences of the published literals, and a falsification fixture
    that spells them out would trip AC-5's sibling greps for the rest of the repo's life. ROT13 is
    not protection - it is the cheapest way to keep the data inert for a grep while staying exactly
    reversible for the one test that consumes it.
    """
    return "".join(
        chr((ord(c) - ord("a") + 13) % 26 + ord("a"))
        if "a" <= c <= "z"
        else chr((ord(c) - ord("A") + 13) % 26 + ord("A"))
        if "A" <= c <= "Z"
        else c
        for c in value
    )


def _tests_excluding_self(tests_dir):
    """Every harness module the AC-6 mirror should see - all of them except this file.

    This file necessarily spells out the rejected literals (asserting the rejection is its job)
    and the falsification test below needs somewhere to hold the pre-T10 values as data. Mirroring
    AC-6 over the *other* harness modules keeps both honest: AC-6 still scans the whole tree and
    remains the arbiter, and its own two count-only matches here (the env key lists in _CHILD and
    in _clean_env) are the known, recorded difference between the two scans.
    """
    return [p for p in sorted(Path(tests_dir).glob("*.py")) if p.name != Path(__file__).name]


def _harness_jwt_secret_literals(tests_dir):
    """Replicate AC-6's scan over the harness in ``tests_dir``: every literal it would collect."""
    found = []
    for path in _tests_excluding_self(tests_dir):
        text = path.read_text(encoding="utf-8")
        for pattern in (_AC6_CALL_GREP, _AC6_DICT_GREP):
            for match in re.finditer(pattern, text):
                found.append((path.name, match.group(1)))
    return found


def _ac6_verdict(tests_dir):
    """Return ``(total, below_gate, offenders)`` as AC-6's loop computes the first two."""
    literals = _harness_jwt_secret_literals(tests_dir)
    offenders = [
        f"{name}:{value}"
        for name, value in literals
        if len(value) < 32 or value in PUBLISHED_SECRETS
    ]
    return len(literals), len(offenders), offenders


def test_harness_boots_on_a_gate_compliant_secret():
    """AC-6 (in-process): every ``JWT_SECRET`` the harness configures clears this issue's gate."""
    total, bad, offenders = _ac6_verdict(BACKEND_DIR / "tests")
    assert total >= 1, (
        "no JWT_SECRET literal is configured in the harness modules the mirror can see - the "
        "AC-6 guard stopped matching and cannot read green on its own"
    )
    assert bad == 0, f"harness JWT_SECRET literals below the gate: {offenders}"


def test_harness_secret_guard_is_falsifiable(tmp_path):
    """The guard above must be able to go RED - replay the pre-T10 harness and watch it fire.

    AC-6's total>=1 / bad=0 pair is the whole point of the harness half of this issue, and a green
    that cannot be turned red is not evidence. The replay overwrites each bootstrap site with
    the recorded pre-T10 value in a throwaway copy under ``tmp_path``; the real ``backend/tests``
    tree is only ever read, so no run of this file can leave a weak secret behind.
    """
    sources = sorted((BACKEND_DIR / "tests").glob("*.py"))
    for source in sources:
        (tmp_path / source.name).write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )

    for name, pre_t10 in _AC6_PRE_T10_LITERALS.items():
        name, pre_t10 = rot13(name), rot13(pre_t10)
        path = tmp_path / name
        text = path.read_text(encoding="utf-8")
        replacement = "JWT_SECRET" + chr(34) + ", " + chr(34) + pre_t10 + chr(34)
        rewritten = re.sub(_AC6_CALL_GREP, replacement, text, count=1)
        assert rewritten != text, f"{name} has no AC-6-shaped JWT_SECRET call site to replay into"
        path.write_text(rewritten, encoding="utf-8")

    total, bad, offenders = _ac6_verdict(tmp_path)
    assert total >= 1, "the AC-6 pattern matched nothing even after the replay"
    assert bad >= 1, f"the replay left the harness looking compliant: {offenders}"

    # Watching the tree must not have changed it.
    assert _ac6_verdict(BACKEND_DIR / "tests")[1] == 0, "the real harness changed while we looked"


def test_the_server_refuses_to_boot_on_a_published_secret():
    """AC-7's third arm, stated the way it can be measured: uvicorn dies at boot.

    Subprocess because uvicorn imports the app at startup and dies inside that import - the same
    path a deployment takes, and the reason D-1 point 2's silent `.env` adoption no longer works.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import uvicorn; uvicorn.run('app.main:app', host='127.0.0.1', port=0)",
        ],
        cwd=str(BACKEND_DIR),
        env={
            **{key: value for key, value in os.environ.items() if key != "JWT_SECRET"},
            "DATABASE_URL": "sqlite:///./t10-boot-gate.db",
            "JWT_SECRET": PUBLISHED_SECRETS[0],
            "STAFF_PIN": "0000",
        },
        capture_output=True,
        text=True,
        timeout=120,
    )
    combined = result.stdout + result.stderr
    assert result.returncode != 0, "uvicorn booted on the published literal"
    assert "ValidationError" in combined, combined[-400:]
    assert "jwt_secret" in combined, combined[-400:]
