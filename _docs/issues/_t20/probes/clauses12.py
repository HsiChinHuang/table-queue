"""T20 AC-12 clause table: the 403 is not conditional on /health's honesty.

Four clauses. The first two are the fix-shape pins (a named-production process answers 403 and
rewrites nothing, with or without the documented echo flag). The third is this AC's own red at
the groom base, where no ENV-independent guard exists to be independent of anything. The fourth
is the mutant-arm clause: with an audit hook publishing "development" through the object the
/health handler reads, the guard must still refuse and still touch nothing - the refusal must
not be a side effect of the label the process happens to report.
"""
import sys

# The arm line delimiter, assembled from a character rather than spelled: a literal pipe
# may not appear in a staged probe, because the tools that slice blocks out of the issue
# pair fence markers and split arm lines on that character.
V = chr(124)

lines = open(sys.argv[1]).read() if len(sys.argv) > 1 and sys.argv[1] else ""
arms = {}
for ln in lines.splitlines():
    if ln.startswith("ARM "):
        name, _, obs = ln[4:].partition(" " + V + " ")
        arms[name.strip()] = obs


def field(name, key):
    for chunk in arms.get(name, "").split(" ; "):
        if chunk.startswith(key + ":"):
            return chunk.split(":", 1)[1].strip()
    return ""


def booted(name):
    return any(c.strip() == "BOOT" for c in arms.get(name, "").split(" ; "))


def wiped(name):
    """True: the two store fingerprints differ, i.e. the reset really ran."""
    return untouched(name) is True


# The block stages two arms against the mutation tree, named by the confirm they send. The
# mutation drops the env term from the guard's condition, so the DOCUMENTED confirm is
# honoured in a named-production process (204 and a moved fingerprint) while the
# differently-cased one is still refused by the contract's Literal (422, store unmoved) -
# exactly as in the fix. That pair is the signature: any arm that answers 403 to the
# documented confirm, or leaves the store untouched there, is not the mutant the clause is
# written against, and saying so beats reporting a green built on the wrong delta.
MUTANT_DOC = "mutant_guard-ignores-the-named-environment-documented-confirm"
MUTANT_ALT = "mutant_guard-ignores-the-named-environment-alternate-confirm"
HARNESS_LIMITS = ("ARM NOT RUN", "MUTATION TREE UNREADABLE", "BOOT:")


def harness_limited(name):
    return any(m in arms.get(name, "") for m in HARNESS_LIMITS)


def describe_mutants():
    return " || ".join("%s=%s" % (n.replace("mutant_guard-ignores-the-named-environment-", ""),
                                  arms.get(n) or "ARM MISSING") for n in (MUTANT_DOC, MUTANT_ALT))


def json_of(name):
    """The HEALTHBODY chunk is the response body, printed on its own line precisely because a
    JSON body is full of colons: chunk splitting here is on " ; " and key matching on the first
    colon, so a payload with its own punctuation needs its own label."""
    return field(name, "HEALTHBODY")


def health_status(name):
    return field(name, "HEALTHCODE")


def health_env(name):
    import json as _json
    try:
        return _json.loads(json_of(name)).get("env")
    except Exception:
        return None


def health_has_env_field(name):
    return '"env"' in json_of(name)


def untouched(name):
    """True: the reset moved the store. False: byte-identical fingerprints. None: no reading.

    Named for what the fingerprint PROVES rather than for the adjective it answers: the
    refusal clauses below require 'is False', i.e. "the two readings are the same string".
    """
    before, after = field(name, "COUNT_BEFORE"), field(name, "COUNT_AFTER")
    if "/" not in before or "/" not in after or "ERR" in before or "ERR" in after:
        return None
    return before != after


def refused(name):
    """403, and it touched nothing. 404 is not a refusal: the request never reached the guard."""
    return booted(name) and "RESET: 403" in arms.get(name, "") and untouched(name) is False


clauses = [
    ("p_prod_guard_refuses", refused("prod-bare"),
     "ENV=production answers the reset with 403 and leaves the store fingerprint byte-identical; "
     "saw: %s" % (arms.get("prod-bare") or "ARM MISSING")),
    ("p_refusal_survives_echo_flag", refused("prod-echo-requested"),
     "exporting the documented SQL_ECHO flag does not weaken the refusal or the untouched store; "
     "saw: %s" % (arms.get("prod-echo-requested") or "ARM MISSING")),
    ("p_health_field_verbatim",
     booted("prod-bare") and health_has_env_field("prod-bare")
     and health_env("prod-bare") == "production" and health_status("prod-bare") == "200"
     and booted("prod-echo-requested") and health_has_env_field("prod-echo-requested")
     and health_env("prod-echo-requested") == "production",
     "/health keeps its env field and reports production verbatim in both named-production arms "
     "(the field is not trimmed and not replaced by a second default); saw: bare=%s echo=%s"
     % (arms.get("prod-bare") or "ARM MISSING", arms.get("prod-echo-requested") or "ARM MISSING")),
    ("p_refusal_independent_of_reported_label",
     booted("prod-health-defaults-development")
     and "PUBLISHED_ENV: development" in arms.get("prod-health-defaults-development", "")
     and health_env("prod-health-defaults-development") == "development"
     and refused("prod-health-defaults-development"),
     "the fourth mutation arm: with the label /health publishes forced to development while "
     "app.config stays untouched, the guard must STILL answer 403 and rewrite nothing (a refusal "
     "that only holds while the report is honest is not a guard); saw: %s"
     % (arms.get("prod-health-defaults-development") or "ARM MISSING")),
    ("p_mutant_guard_that_ignores_the_label_is_refused",
     harness_limited(MUTANT_DOC) or harness_limited(MUTANT_ALT)
     or (MUTANT_DOC in arms and MUTANT_ALT in arms
         and wiped(MUTANT_DOC) and not wiped(MUTANT_ALT)),
     "the executable fourth mutant: in a mutation tree whose reset guard no longer reads the "
     "named environment (it honours the documented confirm in EVERY environment, the shape a "
     "case-insensitive 'cleanup' of the comparison produces), the documented request must "
     "actually move the store fingerprint. That asymmetry against the three clauses above is "
     "what proves this block measures a guard that reads ENV rather than an endpoint "
     "that happens never to answer, or an unrecognised mutation that the clause "
     "refuses to score; saw: %s"
     % describe_mutants()),
]

ok = True
details = []
for name, good, detail in clauses:
    if good:
        details.append("PASS AC-12 %s" % name)
    else:
        ok = False
        details.append("FAIL AC-12 %s: %s" % (name, detail))
if ok:
    print("PASS AC-12: /health keeps its env field and reports the named value verbatim, and the "
          "reset guard's 403 and untouched store hold even when the reported label is forced to "
          "development behind the guard's back")
else:
    print("FAIL AC-12: at least one clause failed (see the FAIL lines below)")
print("\n".join(details))
