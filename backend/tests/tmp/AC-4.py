import os
AC = "AC-4"
FILES = ["backend/app/routers/auth.py", "backend/app/dependencies.py", "backend/app/main.py"]
MISSING = [f for f in FILES if not os.path.isfile(f)]
if MISSING:
    print("FAIL %s: file(s) not found: %s" % (AC, ", ".join(MISSING)))
    raise SystemExit(0)


DOCSTRINGS_ARE_PART_OF_THE_CODE = os.environ.get("T9_GREP_PROSE") == "1"


def body_without_docstrings(text):
    """Drop each function's docstring: prose ABOUT a comparison is not a comparison the code runs.
    This is not cosmetic - the AC-1..AC-3 blocks and this issue's own text name the deleted
    fallback, and a grep over module docstrings would report that prose as a live site."""
    out, i, lines = [], 0, text.split("\n")
    if DOCSTRINGS_ARE_PART_OF_THE_CODE:   # falsification switch, see this AC's Measured today
        return text
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        quote = next((q for q in ('"""', "'''") if stripped.startswith(q)), None)
        if quote:
            if stripped.count(quote) < 2:                     # multi-line: skip to the closing quote
                i += 1
                while i < len(lines) and quote not in lines[i]:
                    i += 1
            i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


hits = []
for f in FILES:
    src = body_without_docstrings(open(f, encoding="utf-8").read())
    for n, line in enumerate(src.split("\n"), 1):
        code = line.split("#")[0].replace("staff_pin_hash", "HASHCOL")
        # Case-folded on purpose: the shipped code writes the lowercase attribute (get_settings()
        # .staff_pin) while the class and the docstrings say Settings.staff_pin. An exact-case grep
        # misses the live line (measured at this base: 0 matches, a false green on a live finding).
        low = code.lower()
        if ".staff_pin" in low and ("==" in code or "!=" in code):
            hits.append("%s:%s: %s" % (f, n, code.strip()))
        if "compare_digest" in code:
            hits.append("%s:%s: plaintext-comparison-primitive in use: %s" % (f, n, line.strip()))
hits = sorted(set(hits))
print("OBS AC-4: plaintext-comparison sites in the auth path: %d%s"
      % (len(hits), "" if not hits else " -> " + " ;; ".join(hits)))
want_sites = int(os.environ.get("T9_WANT_SITES", "0"))   # falsification switch, see Measured today
if len(hits) != want_sites:
    print("FAIL %s: the staff credential is still compared outside the bcrypt hash (%d site(s), want %d) - %s" % (AC, len(hits), want_sites, " ;; ".join(hits) or "none"))
else:
    print("PASS %s: no comparison against the plaintext settings.staff_pin value survives in %s, and no hmac.compare_digest transitional path either - the only PIN verification left is the bcrypt.checkpw call against the stored hash, which the AC-3 probe reads from the live code path rather than from this grep alone" % (AC, ", ".join(FILES)))
