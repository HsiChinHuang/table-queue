import os
AC = "AC-6"
FILES = ["backend/app/routers/auth.py", "backend/app/main.py", "backend/app/seed.py",
         "backend/app/dependencies.py", "backend/app/services/settings.py"]
MISSING = [f for f in FILES if not os.path.isfile(f)]
if MISSING:
    print("FAIL %s: file(s) not found: %s" % (AC, ", ".join(MISSING)))
    raise SystemExit(0)
sites = []
for f in FILES:
    for n, line in enumerate(open(f, encoding="utf-8").read().split("\n"), 1):
        code = line.split("#")[0]
        if "hashpw" in code or "gensalt" in code:
            sites.append((f, n, code.strip()))
offenders = []
for f, n, code in sites:
    g = int(os.environ.get("T9_WANT_COST", "12"))
    if "rounds=" in code:
        try:
            got = int(code.split("rounds=")[1].split(")")[0].split(",")[0])
        except ValueError:
            got = -1
        if got != g:
            offenders.append("%s:%s cost=%s want=%s : %s" % (f, n, got, g, code))
    else:
        offenders.append("%s:%s cost inherited from the bcrypt default rather than pinned : %s" % (f, n, code))
print("OBS AC-6: PIN-hash construction sites: %d ; cost-parameter offenders: %d%s"
      % (len(sites), len(offenders), ("" if not offenders else " -> " + " ;; ".join(offenders))))
if not sites:
    print("FAIL %s: no bcrypt hash construction found in %s, so the cost claim cannot be assessed here" % (AC, ", ".join(FILES)))
elif offenders:
    print("FAIL %s: %d of %d hash-construction site(s) do not pin cost 12 explicitly - %s" % (AC, len(offenders), len(sites), " ;; ".join(offenders)))
else:
    print("PASS %s: all %d PIN-hash construction site(s) in %s pass an explicit rounds=12 to gensalt, so the $2b$12$ cost audit C-18 rated clean is pinned at every writer instead of inherited from a library default that a dependency bump could move" % (AC, len(sites), ", ".join(FILES)))
