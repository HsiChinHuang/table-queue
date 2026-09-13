"""AC-1 clause table: reads the probe's labelled lines, prints one verdict per clause."""
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


def arm(name):
    return arms.get(name, "")


def refused(name):
    """Refused construction: the child died with a validation error before serving."""
    return "BOOT: ValidationError" in arm(name)


_SERVED = ("HEALTH:", "RESET:", "COUNT_BEFORE:", "MAIN_ECHO:", "RESOLVED_ENV:")


def _booted(obs):
    """A served-request label can only appear if the process booted."""
    if not obs:
        return False
    return any(c.strip().startswith(_SERVED) for c in obs.split(" ; "))


def booted_says(name, value):
    obs = arm(name)
    return _booted(obs) and ('"env":"%s"' % value) in obs


clauses = [
    ("p_absent_refused", refused("absent"),
     "with no ENV anywhere Settings refuses construction (want BOOT: ValidationError, saw: %s)" % (arm("absent") or "ARM MISSING")),
    ("p_blank_refused", refused("blank"),
     "with ENV set but empty Settings refuses construction (want BOOT: ValidationError, saw: %s)" % (arm("blank") or "ARM MISSING")),
    ("p_staging_refused", refused("staging"),
     "with ENV=staging outside the allow-list Settings refuses construction (want BOOT: ValidationError, saw: %s)" % (arm("staging") or "ARM MISSING")),
    ("p_dev_boots", booted_says("dev", "development"),
     "with ENV=development the app boots and /health reports development (saw: %s)" % (arm("dev") or "ARM MISSING")),
    ("p_test_boots", booted_says("test", "test"),
     "with ENV=test the app boots and /health reports test (saw: %s)" % (arm("test") or "ARM MISSING")),
    ("p_prod_boots", booted_says("prod", "production"),
     "with ENV=production the app boots and /health reports production (saw: %s)" % (arm("prod") or "ARM MISSING")),
]

green = True
details = []
for name, ok, detail in clauses:
    if ok:
        details.append("PASS AC-1 %s" % name)
    else:
        green = False
        details.append("FAIL AC-1 %s: %s" % (name, detail))

if green:
    print("PASS AC-1: Settings refuses construction when ENV is absent, empty or outside "
          + V.join(("development", "test", "production"))
          + ", and boots with /health reporting exactly the explicit value for each of the "
            "three allowed environments")
else:
    print("FAIL AC-1: at least one clause failed (see the FAIL lines below)")
print("\n".join(details))
