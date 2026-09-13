"""T20 AC-7 clause table: the fixed tree boots under every named environment and its suite runs.

Reads the probe's labelled lines. Each boot clause requires the process to serve /health, to
report the environment it was named with, and to leave SQL echo off; the refused arm requires
the opposite (no answer at all). The suite clause is the whole-suite regression gate: it is
the clause that catches a fix that satisfies every pin in this issue and leaves the
application unimportable or the test harness broken.
"""
import sys

# The arm line delimiter, assembled from a character rather than spelled: a literal pipe may
# not appear in a staged probe, because the tools that slice blocks out of the issue pair
# fence markers and split arm lines on that character. probe9.py checks that the bytes a
# block stages are exactly these bytes, so the check has to deny itself too.
V = chr(124)
lines = open(sys.argv[1]).read() if len(sys.argv) > 1 and sys.argv[1] else ""


def arm(name):
    for ln in lines.splitlines():
        if ln.startswith("ARM " + name + " " + V):
            return ln.split(V, 1)[1].strip()
    return ""


def served(name):
    obs = arm(name)
    return bool(obs) and any(c.strip().startswith("HEALTH: 200") for c in obs.split(" ; "))


def reports(name, value):
    return served(name) and ('"env":"%s"' % value) in arm(name)


def echo_off(name):
    obs = arm(name)
    return served(name) and any(c.strip() == "MAIN_ECHO: False" for c in obs.split(" ; "))


tail = arm("suite-harness-env")
clauses = [
    ("boot_refused_without_ENV", "BOOT: ValidationError" in arm("boot-absent")
     and "HEALTH:" not in arm("boot-absent"),
     "a process whose environment never names ENV must be refused before it answers; saw: %r"
     % (arm("boot-absent") or "ARM MISSING")),
    ("boot_development_serves", reports("boot-development", "development") and echo_off("boot-development"),
     "ENV=development must boot, report development and leave statement echo off; saw: %r"
     % (arm("boot-development") or "ARM MISSING")),
    ("boot_test_serves", reports("boot-test", "test") and echo_off("boot-test"),
     "ENV=test must boot, report test and leave echo off; saw: %r"
     % (arm("boot-test") or "ARM MISSING")),
    ("boot_production_serves", reports("boot-production", "production") and echo_off("boot-production"),
     "ENV=production must boot, report production and leave echo off; saw: %r"
     % (arm("boot-production") or "ARM MISSING")),
    ("whole_suite_passes", " passed" in tail and " error" not in tail and " failed" not in tail,
     "the entire backend suite must pass in an environment that supplies only the gate variables "
     "and never names ENV; saw: %r" % (tail or "ARM MISSING")),
]

ok = True
details = []
for name, good, detail in clauses:
    if good:
        details.append("PASS AC-7 %s" % name)
    else:
        ok = False
        details.append("FAIL AC-7 %s: %s" % (name, detail))
if ok:
    print("PASS AC-7: the tree under test refuses an unnamed environment, boots and serves under "
          "each of the three named ones with echo off, and its whole backend suite passes")
else:
    print("FAIL AC-7: at least one clause failed (see the FAIL lines below)")
print("\n".join(details))
