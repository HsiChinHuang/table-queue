"""T20 AC-2 clause table: one verdict line per reset-guard clause, then the verdict token.

Reads the probe's labelled ARM lines. The store fingerprint behind each COUNT_* line is
"<waitlist rows>/<first 7 chars of the stored staff_pin_hash>/<max updated_at>", so both
halves of the A-3 damage (schema rewrite and credential rollback) are observable, and a
403 that touched nothing leaves the two fingerprints identical.
"""
import os
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


def changed(name):
    """True: the store really was rewritten. False: untouched. None: could not tell."""
    before, after = field(name, "COUNT_BEFORE"), field(name, "COUNT_AFTER")
    if "/" not in before or "/" not in after or "ERR" in before or "ERR" in after:
        return None
    rows_b, rows_a = before.split("/")[0], after.split("/")[0]
    try:
        int(rows_b), int(rows_a)
    except ValueError:
        return None
    return before != after


def refused(name):
    return "BOOT: ValidationError" in arms.get(name, "")


_SERVED = ("HEALTH:", "RESET:", "COUNT_BEFORE:", "MAIN_ECHO:", "RESOLVED_ENV:")


def _booted(obs):
    """A served-request label can only appear if the process booted."""
    return bool(obs) and any(c.strip().startswith(_SERVED) for c in obs.split(" ; "))


def untouchable(name):
    return (_booted(arms.get(name, ""))
            and "RESET: 403" in arms.get(name, "")
            and changed(name) is False)


clauses = [
    ("p_absent_reset_403", refused("absent") or untouchable("absent"),
     "with ENV unset the wipe is NOT armed: want the process refused at boot (D-1) or a RESET 403 "
     "that leaves the store fingerprint byte-identical; it must never answer 204; saw: %s" % (arms.get("absent") or "ARM MISSING")),
    ("p_test_reset_403", untouchable("test"),
     "with ENV=test the wipe is not armed (the control that the guard is not merely broken): want RESET 403, fingerprint unchanged; saw: %s" % (arms.get("test") or "ARM MISSING")),
    ("p_prod_reset_403", untouchable("production"),
     "with ENV=production the wipe is not armed: want RESET 403, fingerprint unchanged; saw: %s" % (arms.get("production") or "ARM MISSING")),
    ("p_dev_reset_reachable", _booted(arms.get("development", ""))
     and "RESET: 204" in arms.get("development", "")
     and changed("development") is True,
     "with ENV EXPLICITLY development the dev convenience survives: want BOOT ok, RESET 204 and the store actually rewritten; saw: %s" % (arms.get("development") or "ARM MISSING")),
]

ok = True
details = []
for name, good, detail in clauses:
    if good:
        details.append("PASS AC-2 %s" % name)
    else:
        ok = False
        details.append("FAIL AC-2 %s: %s" % (name, detail))
if ok:
    print("PASS AC-2: /api/v1/admin/reset answers 403 and rewrites nothing unless the process was booted with "
          "ENV explicitly development; development keeps the documented reset exactly where it is documented")
else:
    print("FAIL AC-2: at least one clause failed (see the FAIL lines below)")
print("\n".join(details))
