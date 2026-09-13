"""T20 AC-3 clause table: /health reports the explicit value or the process never booted."""
import json
import sys

# The arm line delimiter, assembled from a character rather than spelled: a literal pipe may
# not appear in a staged probe, because the tools that slice blocks out of the issue pair
# fence markers and split arm lines on that character. probe9.py checks that the bytes a
# block stages are exactly these bytes, so the check has to deny itself too.
V = chr(124)
lines = open(sys.argv[1]).read() if len(sys.argv) > 1 and sys.argv[1] else ""
arms = {}
for ln in lines.splitlines():
    if ln.startswith("ARM "):
        name, _, obs = ln[4:].partition(" " + V + " ")
        arms[name.strip()] = obs


def body_env(name):
    """The env value /health actually reported, or None if it never answered with JSON."""
    for chunk in arms.get(name, "").split(" ; "):
        if chunk.startswith("HEALTH:"):
            parts = chunk.split(" ", 2)
            if len(parts) == 3:
                try:
                    return json.loads(parts[2]).get("env")
                except Exception:
                    return None
    return None


def refused(name):
    return "BOOT: ValidationError" in arms.get(name, "")


def status_ok(name):
    return "HEALTH: 200 " in arms.get(name, "")


clauses = [
    ("p_absent_never_answers", refused("env-absent"),
     "a process with no ENV never reaches the point of answering /health (want BOOT: ValidationError, i.e. no implicit development is ever publishable); saw: %s" % (arms.get("env-absent") or "ARM MISSING")),
    ("p_dev_reports_dev", status_ok("env-development") and body_env("env-development") == "development",
     "with ENV=development /health reports development; saw: %s" % (arms.get("env-development") or "ARM MISSING")),
    ("p_test_reports_test", status_ok("env-test") and body_env("env-test") == "test",
     "with ENV=test /health reports test (control: the field tracks the variable, it is not a second default); saw: %s" % (arms.get("env-test") or "ARM MISSING")),
    ("p_prod_reports_prod", status_ok("env-production") and body_env("env-production") == "production",
     "with ENV=production /health reports production, so the externally readable state can never name development by omission; saw: %s" % (arms.get("env-production") or "ARM MISSING")),
]

ok = True
details = []
for name, good, detail in clauses:
    if good:
        details.append("PASS AC-3 %s" % name)
    else:
        ok = False
        details.append("FAIL AC-3 %s: %s" % (name, detail))
if ok:
    print("PASS AC-3: /health keeps its env field and reports exactly the explicit ENV value; with no ENV the "
          "process refuses to boot, so no implicit environment is ever externally confirmable")
else:
    print("FAIL AC-3: at least one clause failed (see the FAIL lines below)")
print("\n".join(details))
