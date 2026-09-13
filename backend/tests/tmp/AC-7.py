import os, re
AC = "AC-7"
FILES = ["_docs/openapi.yaml", "README.md", "_docs/deployment.md", "_docs/specs.md", "backend/.env.example"]
MISSING = [f for f in FILES if not os.path.isfile(f)]
if MISSING:
    print("FAIL %s: file(s) not found: %s" % (AC, ", ".join(MISSING)))
    raise SystemExit(0)
WANTED = r"staff_pin_hash|staff PIN|auth/login|change-pin|STAFF_PIN"
PIN_IN_TEXT = r"\b1234\b|\b0000\b"
stale, pin_refs, missing = [], [], []
for f in FILES:
    for n, line in enumerate(open(f, encoding="utf-8").read().split("\n"), 1):
        low = line.lower()
        if re.search(WANTED, line, re.I) and re.search(PIN_IN_TEXT, line):
            stale.append("%s:%s: %s" % (f, n, line.strip()[:100]))
        if re.search(r"STAFF_PIN|staff_pin", line):
            pin_refs.append("%s:%s" % (f, n))
# the env contract itself must still be documented (D-1: STAFF_PIN stays the one-time seed source)
if not pin_refs:
    missing.append("no STAFF_PIN mention anywhere in the contract files, so the one-time seed contract is undocumented")
print("OBS AC-7: staff-PIN contract files that quote a concrete PIN value: %d ; STAFF_PIN mentions across those files: %d"
      % (len(stale), len(pin_refs)))
for s in stale[:6]:
    print("  QUOTE AC-7: " + s)
if stale:
    print("FAIL %s: %d contract line(s) pair the staff-PIN contract with a concrete PIN value, which is the copy-paste credential D-5 measured - %s" % (AC, len(stale), " ;; ".join(s[:40] for s in stale)))
elif missing:
    print("FAIL %s: %s" % (AC, "; ".join(missing)))
else:
    print("PASS %s: no contract file (_docs/openapi.yaml, README.md, _docs/deployment.md, _docs/specs.md, backend/.env.example) pairs the staff-PIN contract with a concrete PIN value, while the STAFF_PIN variable itself stays documented %d time(s) as the one-time bootstrap seed of AC-1" % (AC, len(pin_refs)))
