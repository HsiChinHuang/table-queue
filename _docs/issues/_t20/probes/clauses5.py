"""T20 AC-5 clause table: echo is explicit-or-off, and the label never arms it.

Reads the probe's labelled ARM lines. Two shapes of evidence are required, and both are
stated in the clauses: the DEFAULT is off in every environment label (so the
echo=settings.env == "development" coupling is gone), and an EXPLICIT operator request
still arms both engines (so the flag is a real setting and not a deleted line). The
default arm with no ENV is deliberately satisfied by either outcome T20 D-1 permits - a
refused boot, or a boot with echo off - because this AC owns the echo coupling and AC-1
owns the refusal; requiring the refusal here would double-book it.
"""
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


def field(name, key):
    for chunk in arms.get(name, "").split(" ; "):
        if chunk.startswith(key + ":"):
            return chunk.split(":", 1)[1].strip()
    return ""


def num(name, key):
    try:
        return int(field(name, key))
    except ValueError:
        return None


def booted(name):
    """The engine imported. A refusal shows up inside the flag as BOOT_ValidationError."""
    return "BOOT_" not in arms.get(name, "") and "MAIN_ECHO:" in arms.get(name, "")


def echo_on(name):
    return field(name, "MAIN_ECHO") == "True" or field(name, "SEED_ECHO") == "True"


def echo_off(name):
    return booted(name) and not echo_on(name)


clauses = [
    ("p_default_off_env_absent", (not booted("env=None;echo=None")) or echo_off("env=None;echo=None"),
     "no ENV and no echo request: the process must refuse to boot (AC-1's D-1) or boot with BOTH engines off; it must not boot with echo armed (saw: %s)" % (arms.get("env=None;echo=None") or "ARM MISSING")),
    ("p_default_off_in_development", echo_off("env=development;echo=None"),
     "ENV=development alone must NOT arm echo - the coupling this issue exists to break (want MAIN_ECHO False SEED_ECHO False) (saw: %s)" % (arms.get("env=development;echo=None") or "ARM MISSING")),
    ("p_default_off_in_test", echo_off("env=test;echo=None"),
     "ENV=test with no echo request: both engines off (saw: %s)" % (arms.get("env=test;echo=None") or "ARM MISSING")),
    ("p_default_off_in_production", echo_off("env=production;echo=None"),
     "ENV=production with no echo request: both engines off (saw: %s)" % (arms.get("env=production;echo=None") or "ARM MISSING")),
    ("p_explicit_true_arms", echo_on("env=production;echo=true") and echo_on("env=development;echo=true"),
     "SQL_ECHO=true MUST arm BOTH engines in every environment, so the flag is a real setting and not a deleted line (want MAIN_ECHO True and SEED_ECHO True in the production and development echo=true arms) (saw: prod=%s/%s dev=%s/%s)" % (
         field("env=production;echo=true", "MAIN_ECHO"), field("env=production;echo=true", "SEED_ECHO"),
         field("env=development;echo=true", "MAIN_ECHO"), field("env=development;echo=true", "SEED_ECHO"))),
    ("p_explicit_false_off", echo_off("env=development;echo=false"),
     "SQL_ECHO=false in development stays off (saw: %s)" % (arms.get("env=development;echo=false") or "ARM MISSING")),
    ("p_no_pii_in_default_log", num("join-development", "ECHO_LINES") == 0 and num("join-development", "PII_LINES") == 0,
     "one real guest join on ENV=development with no echo request writes zero sqlalchemy echo lines and zero PII lines to the process log (want ECHO_LINES 0 and PII_LINES 0) (saw: %s)" % (arms.get("join-development") or "ARM MISSING")),
]

ok = True
details = []
for name, good, detail in clauses:
    if good:
        details.append("PASS AC-5 %s" % name)
    else:
        ok = False
        details.append("FAIL AC-5 %s: %s" % (name, detail))
if ok:
    print("PASS AC-5: engine echo is decoupled from the environment label and off by default on both engines "
          "(app/database.py and app/seed.py), arms only on an explicit request, and the default process log "
          "carries no bound guest PII")
else:
    print("FAIL AC-5: at least one clause failed (see the FAIL lines below)")
print("\n".join(details))
