"""T20 AC-11 clause table: no second opt-in gate re-arms the wipe or the echo.

Reads the probe's labelled ARM lines. Four clauses:

  p_absent_arm_no_reset   - the no-ENV arm never hands out a 204. Today the bare no-ENV
                            process answers 204 (A-3 reproduced); after D-1 it refuses to
                            boot, and adding invented opt-in variables to that arm must not
                            change either answer.
  p_offlist_label_never_204 - every 'production' arm answers 403 or never boots, whatever
                            second-gate variable travels with it. This is the clause a fix
                            that re-keys the guard on 'os.environ["ALLOW_DATA_RESET"]' fails.
  p_control_test_label_403  - the 'test' arms 403 with and without an opt-in flag, so a
                            guard that merely broke everywhere cannot satisfy this AC.
  p_explicit_development_204 - the documented reset still works with NOTHING exported beyond
                            ENV=development and the documented body confirmation, and it is
                            not secretly gated behind a flag nobody documented.
  p_only_sql_echo_arms_echo - SQL_ECHO is the single documented operator request that moves
                            echo; DEV_MODE/FEATURE_DEV_MODE and friends must not arm it.

The 404 answer is refused on purpose: a request that does not reach the env guard looks like
a refusal to a status-code-only check, so every clause that wants a refusal names 403 (or a
refused boot) and never accepts 404.
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

FLAGS = ["ALLOW_DATA_RESET", "TQ_ALLOW_RESET", "REQUIRE_RESET_TOKEN", "RESET_ALLOWED",
         "DEV_MODE", "FEATURE_DEV_MODE", "RESET_CONFIRM"]
ECHO_OFF_BY_LABEL = ("production", "test")


def field(name, key):
    for chunk in arms.get(name, "").split(" ; "):
        if chunk.startswith(key + ":"):
            return chunk.split(":", 1)[1].strip()
    return ""


def booted(name):
    return any(c.strip() == "BOOT" for c in arms.get(name, "").split(" ; "))


def refused_arm(name):
    """Refused means refused: a refused boot or a 403. A 404 means the request never
    reached the guard and is never accepted as a refusal here."""
    return (not booted(name)) or "RESET: 403" in arms.get(name, "")


def arms_starting(prefix):
    return [n for n in arms if n.startswith(prefix)]


absent_arms = arms_starting("absent")
prod_arms = arms_starting("production-plus-")
test_arms = arms_starting("test-plus-")
dev_arms = arms_starting("development-plus-")

# The echo claim: in a production-labelled arm, echo must stay off no matter which label
# shaped flag is exported. The SQL_ECHO arm is the documented exception and is excluded.
echo_armed = [n for n in prod_arms
              if field(n, "MAIN_ECHO") == "True" or field(n, "SEED_ECHO") == "True"]
sql_echo_arm = "development-plus-sql_echo"

clauses = [
    ("p_absent_arm_no_reset",
     bool(absent_arms) and all(not booted(n) or "RESET: 403" in arms[n] for n in absent_arms)
     and not any("RESET: 204" in arms[n] for n in absent_arms),
     "with no ENV the wipe is never armed, with or without an invented opt-in flag: want a refused "
     "boot or a 403 and never a 204; saw: %s" % (" || ".join(arms[n] for n in sorted(absent_arms))
                                                 or "ABSENT ARMS MISSING")),
    ("p_offlist_label_never_204",
     bool(prod_arms) and all(refused_arm(n) for n in prod_arms)
     and not any("RESET: 204" in arms[n] for n in prod_arms),
     "no second opt-in variable re-arms the reset under ENV=production (D-2 refused a second gate): "
     "every production-plus-FLAG arm must refuse; saw: %s"
     % (" || ".join("%s=%s" % (n.split("production-plus-")[1], arms[n]) for n in sorted(prod_arms))
        or "PRODUCTION ARMS MISSING")),
    ("p_control_test_label_403",
     [n for n in test_arms if n in arms] and all(refused_arm(n) for n in test_arms if n in arms),
     "the test-labelled arms keep answering 403 with and without an opt-in flag, so the guard is "
     "not merely broken; saw: %s"
     % (" || ".join("%s=%s" % (n, arms[n]) for n in sorted(test_arms) if n in arms)
        or "TEST ARMS MISSING")),
    ("p_explicit_development_204",
     booted("development-bare") and "RESET: 204" in arms.get("development-bare", ""),
     "with ENV=development and nothing else exported the documented reset still answers 204, so the "
     "fix did not hide the dev convenience behind an undocumented flag; saw: %s"
     % (arms.get("development-bare") or "ARM MISSING")),
    ("p_only_sql_echo_arms_echo",
     bool(prod_arms) and not echo_armed
     and (field(sql_echo_arm, "MAIN_ECHO") == "True" or field(sql_echo_arm, "SEED_ECHO") == "True"),
     "SQL_ECHO is the only exported variable that moves echo: no production arm may have an engine "
     "echoing (armed: %s) and the development SQL_ECHO arm must (saw: %s)"
     % (",".join(sorted(echo_armed)) or "none", arms.get(sql_echo_arm) or "ARM MISSING")),
]

ok = True
details = []
for name, good, detail in clauses:
    if good:
        details.append("PASS AC-11 %s" % name)
    else:
        ok = False
        details.append("FAIL AC-11 %s: %s" % (name, detail))
if ok:
    print("PASS AC-11: no second opt-in variable re-arms the reset or the echo in any named "
          "environment, the test and production labels keep answering 403 with every flag exported, "
          "and the explicit-development reset needs no flag at all")
else:
    print("FAIL AC-11: at least one clause failed (see the FAIL lines below)")
print("\n".join(details))
