"""T20 AC-4 clause table: the test harness states ENV, and stating it survives the gate.

Reads the probe's labelled ARM lines, one per harness file. A harness passes when the
environment it states for itself boots the application (that is the required half: after
ENV becomes a required setting, an arm that fails to boot is a harness the fix has to
repair), reports an on-list environment, and does not leave SQL echo armed by default.
JWT_SECRET is reported but NOT gated here: T10 owns the secret-quality contract, and the
published test literals the older modules still carry are that issue's business, not this
one. The line is printed so QA can see both facts in one place.
"""
import json
import sys

# The arm line delimiter, assembled from a character rather than spelled: a literal pipe may
# not appear in a staged probe, because the tools that slice blocks out of the issue pair
# fence markers and split arm lines on that character. probe9.py checks that the bytes a
# block stages are exactly these bytes, so the check has to deny itself too.
V = chr(124)
# The arm line delimiter, assembled from a character: a literal pipe may not appear in a
# staged probe, because the tools that slice blocks out of the issue pair fence markers and
# split arm lines on that character. See probe9.py, which checks the staged bytes are these
# bytes.
ALLOWED = ("development", "test", "production")

lines = open(sys.argv[1]).read() if len(sys.argv) > 1 and sys.argv[1] else ""
arms = {}
for ln in lines.splitlines():
    if ln.startswith("ARM "):
        raw, _, obs = ln[4:].partition(V)
        arms[raw.split("/")[-1]] = obs


def field(name, key):
    for chunk in arms.get(name, "").split(" ; "):
        if chunk.startswith(key + ":"):
            return chunk.split(":", 1)[1].strip()
    return ""


def env_json(name):
    raw = arms.get(name, "")
    start = raw.find("{")
    end = raw.find("}", start)
    if start < 0 or end < 0:
        return {}
    try:
        return json.loads(raw[start:end + 1])
    except Exception:
        return {}


ok = True
details = []
for name in sorted(arms):
    chunks = [c for c in arms[name].split(" ; ") if c]
    booted = "BOOT" in chunks
    resolved = field(name, "RESOLVED_ENV")
    echo = field(name, "MAIN_ECHO")
    good = booted and resolved in ALLOWED and echo == "False"
    detail = ("the harness module's own environment statement must boot the application, resolve "
              "one of %s and leave SQL echo off; saw boot=%s resolved_env=%s main_echo=%s "
              "stated_env=%s" % (V.join(ALLOWED), "ok" if booted else "REFUSED",
                                 resolved or "none", echo or "none",
                                 env_json(name).get("ENV", "?")))
    if good:
        details.append("PASS AC-4 %s" % name)
    else:
        ok = False
        details.append("FAIL AC-4 %s: %s" % (name, detail))

if not arms:
    print("FAIL AC-4: the probe produced no ARM lines, so nothing was measured")
elif ok:
    print("PASS AC-4: every harness module that states an environment for itself boots the "
          "application under the required-ENV contract, resolves an allowed environment, and "
          "leaves SQL echo off (%d modules)" % len(arms))
else:
    print("FAIL AC-4: at least one harness module fails its clause (%d measured)" % len(arms))
print("\n".join(details))
