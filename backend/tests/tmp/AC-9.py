import hashlib, os, subprocess
AC = "AC-9"
PROBES = ["AC-1.py", "AC-2.py", "AC-3.py", "AC-4.py", "AC-5.py", "AC-6.py", "AC-7.py", "AC-8.py",
          "AC-9.py", "seedrow.py"]
HERE = os.path.dirname(os.path.abspath(__file__))
# Self-describing by design: this block reports the digest of every probe it was handed, and pins the
# digests of the probes that carry an ASSERTION. Why pin at all - the cheapest probe in this issue is
# the one that reads a source file, and a writer under time pressure can satisfy AC-4/AC-6/AC-7 by
# editing the probe instead of the product. A digest cannot be argued with, and it is computed from
# bytes rather than from an intention: the assertion side of an issue belongs to the PM, so if it
# moved, this run has to say so even when the number it now prints is the number the AC wanted.
WANT = {
    "AC-1.py": "bbe7b899ca28c846",
    "AC-2.py": "ed4c4691a1c844e7",
    "AC-3.py": "9a22fa5bc9fc1235",
    "AC-4.py": "5946e7fb509c66de",
    "AC-5.py": "dacdbfe526f96990",
    "AC-6.py": "11b8fa7307bbf48c",
    "AC-7.py": "0a6f5d8f2f18cbd8",
    "AC-8.py": "7f1f541f7f6facda",
    "seedrow.py": "7a82829d78246f29",
}
missing = [p for p in PROBES if not os.path.isfile(os.path.join(HERE, p))]
if missing:
    print("FAIL %s: probe script(s) missing from the scratch dir: %s" % (AC, ", ".join(missing)))
    raise SystemExit(0)
got = {p: hashlib.sha256(open(os.path.join(HERE, p), "rb").read()).hexdigest()[:16] for p in PROBES}
print("DIGESTS AC-9: " + " ".join("%s=%s" % (p, got[p]) for p in PROBES))
bad = [("%s=%s_want_%s" % (p, got[p], w)) for p, w in sorted(WANT.items()) if got.get(p) != w]
if len(WANT) != len(PROBES) - 1:
    bad.append("only %d of %d probes are pinned, so an unpinned probe could be rewritten freely" % (len(WANT), len(PROBES)))
linked = [p for p in PROBES
          if not os.path.isfile(os.path.join(HERE, p)) or os.path.islink(os.path.join(HERE, p))]
if linked:
    bad.append("probe(s) are a link rather than a real file in this tree, so their digest is not a "
               "measurement of this tree: " + ", ".join(linked))
r = subprocess.run(["git", "status", "--porcelain", "--", "backend/app", "backend/tests",
                    "frontend/src", "_docs/openapi.yaml", "README.md", "_docs/deployment.md",
                    "_docs/specs.md", "backend/.env.example"], capture_output=True, text=True)
lines = [l for l in r.stdout.splitlines() if l.strip() and "tests/tmp" not in l]
print("OBS AC-9: product/docs/contract change lines in this tree (scratch excluded): %d%s"
      % (len(lines), ("" if not lines else " -> " + "; ".join(l[:44] for l in lines[:8]))))
if bad:
    print("FAIL %s: assertion-side drift - %s" % (AC, " ;; ".join(bad)))
else:
    print("PASS %s: all %d pinned probe scripts still carry their groom-time digests and none of them is a link into another tree, so no assertion in this issue was edited to buy a green; the change set this run measured is %d line(s) under backend/app, backend/tests, frontend/src, _docs/openapi.yaml, README.md, _docs/deployment.md, _docs/specs.md or backend/.env.example" % (AC, len(WANT), len(lines)))
