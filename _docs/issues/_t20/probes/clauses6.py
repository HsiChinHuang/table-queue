"""T20 AC-6 clause table: the contract change is written down, and the documented boot works.

Two document clauses and one behaviour clause, kept apart on purpose: the document can be
correct while the suite is broken by the change, and the suite can be repaired while the
document still promises an optional ``ENV``. Both halves are measured from the tree under
test - the README text is read as shipped, and the suite runs with an environment the probe
built itself (``PYTEST_ADDOPTS=-p no:cacheprovider`` keeps ``.pytest_cache`` out of the tree
so AC-8's cleanliness clause is not contaminated by running this block first).

The document clauses are keyed on the README's *required* column rather than on prose: the
row must stop promising a ``development`` default and must say the variable is required, and
the document must name every allowed value somewhere.
"""
import re
import sys

lines = open(sys.argv[1]).read() if len(sys.argv) > 1 and sys.argv[1] else ""
whole = lines


def fact(key):
    for ln in lines.splitlines():
        if ln.startswith(key + ":"):
            return ln.split(":", 1)[1].strip()
    return ""


def arm(name):
    for ln in lines.splitlines():
        if ln.startswith("ARM " + name + " |"):
            return ln.split("|", 1)[1].strip()
    return ""


def required_column_says_required(row):
    """The README table's Required column (4th cell) must read yes, and the Default cell
    must no longer be a permissive environment name."""
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    if len(cells) < 4:
        return False
    _var, default, required = cells[0], cells[1], cells[2]
    return required.lower() in ("yes", "true", "required") and default.strip().lower() not in (
        "development", "test", "production", "none", "", "-", "-"
    )


row = fact("README_ENV_ROW")
values = fact("README_ENV_VALUES")
tail = arm("suite")

clauses = [
    ("doc_env_row_is_required_not_defaulted",
     bool(row) and required_column_says_required(row),
     "the README's ENV row must stop presenting the permissive value as a default and must mark the "
     "variable required (row form: '| ENV | <no permissive default> | yes | <description> |'); saw: %r"
     % (row or "no ENV row found"),),
    ("doc_names_allowed_values",
     all(v in values for v in ("development", "test", "production")),
     "the document must name every allowed value so an operator can choose without reading source; "
     "saw: %r" % (values or "none"),),
    ("suite_boots_without_an_external_ENV",
     " passed" in tail and " error" not in tail and " failed" not in tail,
     "the whole backend suite must pass with an environment that supplies only the gate variables "
     "(JWT_SECRET, STAFF_PIN, DATABASE_URL) and NO ENV, proving the suite states its own environment; "
     "saw: %r" % (tail or "no pytest tail"),),
]

ok = True
details = []
for name, good, detail in clauses:
    if good:
        details.append("PASS AC-6 %s" % name)
    else:
        ok = False
        details.append("FAIL AC-6 %s: %s" % (name, detail))
if ok:
    print("PASS AC-6: the README states ENV as required with no permissive default, names every "
          "allowed value, and the backend suite passes with an environment that never names ENV")
else:
    print("FAIL AC-6: at least one clause failed (see the FAIL lines below)")
print("\n".join(details))
