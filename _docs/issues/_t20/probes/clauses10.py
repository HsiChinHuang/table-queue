"""T20 AC-10 clause table: the documents stop documenting ENV as optional development.

Four clauses, three of them greps over the two documents an operator actually reads
(README.md's backend variable table and _docs/deployment.md's environment table plus its
deployment instruction). Each refusal clause is this AC's red at the groom base; the fourth
is a green pin on the parts of the documents that are already correct and must survive.

This block owns the DOCUMENT half of the contract change. It deliberately does not run the
suite or boot the application: AC-6 owns 'the documented boot still works', and a docs block
that also ran 300 tests could not tell a stale row from a broken harness.
"""
import sys

# The arm line delimiter, assembled from a character rather than spelled: a literal pipe
# may not appear in a staged probe, because the tools that slice blocks out of the issue
# pair fence markers and split arm lines on that character.
V = chr(124)

lines = open(sys.argv[1]).read() if len(sys.argv) > 1 and sys.argv[1] else ""


def fact(key):
    for ln in lines.splitlines():
        if ln.startswith(key + ":"):
            return ln.split(":", 1)[1].strip()
    return ""


def cells(row):
    return [c.strip() for c in row.split("\t")]


def row_is_required_no_default(row):
    """'<VAR>\\t<no permissive default>\\tyes\\t<description naming the allow-list>'.

    The Required cell (third) must read yes, the Default cell (second) must no longer be an
    environment name or a placeholder, and the row must name all three allowed values so an
    operator can choose without reading source.
    """
    c = cells(row)
    if len(c) < 4 or c[0] != "ENV":
        return False
    if c[2].lower() not in ("yes", "true", "required"):
        return False
    if c[1].strip().lower() in ("development", "test", "production", "", "none", "-", "(none)"):
        return False
    if any(v not in row for v in ("development", "test", "production")):
        return False
    return True


row_readme = fact("README_ENV_ROW")
row_deploy = fact("DEPLOY_ENV_ROW")
line_deploy = fact("DEPLOY_ENV_LINE")
try:
    claims = int(fact("DOCS_DEFAULT_CLAIM_COUNT"))
except ValueError:
    claims = None

clauses = [
    ("readme_env_row_required",
     row_is_required_no_default(row_readme),
     "the README's ENV row must mark the variable required, carry no permissive default and name "
     "development|test|production (row shape: ENV, a non-environment default cell, yes, then a description); saw: %r"
     % (row_readme or "no ENV row in README.md")),
    ("deploy_env_row_required",
     row_is_required_no_default(row_deploy),
     "deployment.md's ENV row must carry the same required/no-default/allow-list shape; saw: %r"
     % (row_deploy or "no ENV row in _docs/deployment.md")),
    ("no_bare_production_instruction",
     line_deploy == "",
     "deployment.md must not carry a bare 'Set ENV=production.' instruction that names one value "
     "without saying the variable is required and what the other values mean; saw: %r"
     % (line_deploy or "none")),
    ("no_surviving_optional_default_claim",
     claims == 0,
     "zero lines in README.md or deployment.md may still describe ENV as optional or as defaulting "
     "to development; saw: %s" % ("ARM MISSING" if claims is None else claims)),
]

ok = True
details = []
for name, good, detail in clauses:
    if good:
        details.append("PASS AC-10 %s" % name)
    else:
        ok = False
        details.append("FAIL AC-10 %s: %s" % (name, detail))
if ok:
    print("PASS AC-10: README.md and _docs/deployment.md both document ENV as required with no "
          "permissive default and name the whole allow-list, no bare ENV=production instruction "
          "survives, and no line still calls ENV optional or development-defaulted")
else:
    print("FAIL AC-10: at least one clause failed (see the FAIL lines below)")
print("\n".join(details))
