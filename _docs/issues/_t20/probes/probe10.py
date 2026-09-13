"""T20 AC-10 probe: the operator-facing documents stop documenting the fail-open.

Three facts, all read from the tree under test without booting anything. The audit's
A-1/D-2 exposure is not only the defaulted field in backend/app/config.py: an operator who
follows the shipped documents is told, in three places, that the permissive value is the
default and that naming the variable is optional. A fix that edits config.py and leaves
these rows untouched repairs the code and keeps the promise of the old contract, and the
next round that reads the document re-introduces the default with a straight face.

''README_ENV_ROW''            - the README's ENV row, read as shipped (tab-delimited table).
''DEPLOY_ENV_ROW''            - deployment.md's ENV row in the same shape.
''DEPLOY_ENV_LINE''           - the bare 'Set ENV=production' instruction, if it still stands
                                alone without naming what the other values mean or that the
                                variable is now mandatory.
''DOCS_DEFAULT_CLAIM_COUNT''  - how many lines in either document still say ENV is optional
                                or defaults to development.

Nothing is written into the tree: every scratch file lives under the scratch directory, so
running this block never dirties git status.
"""
import re
from pathlib import Path

# The arm line delimiter, assembled from a character rather than spelled: a literal pipe
# may not appear in a staged probe, because the tools that slice blocks out of the issue
# pair fence markers and split arm lines on that character. probe9.py checks that the bytes
# a block stages are exactly these bytes, so the check has to deny itself too.
V = chr(124)

README = Path("README.md")
DEPLOY = Path("_docs/deployment.md")


def read(path):
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def env_row(text):
    """The ENV row of a tab-delimited variable table, or the empty string."""
    for ln in text.splitlines():
        if re.match(r"^\s*ENV\s+\S", ln):
            return ln.strip()
    return ""


readme = read(README)
deploy = read(DEPLOY)

print("README_ENV_ROW: %s" % env_row(readme), flush=True)
print("DEPLOY_ENV_ROW: %s" % env_row(deploy), flush=True)

# The bare production instruction: a line that only tells the operator to set one value.
weak = [ln.strip() for ln in deploy.splitlines()
        if re.match(r"^\s*[-*]?\s*Set ['\"]?ENV=production['\"]?\.?\s*$", ln)]
print("DEPLOY_ENV_LINE: %s" % (weak[0] if weak else ""), flush=True)

# The "not a table cell" separator is the pipe character, assembled rather than spelled:
# a staged probe may not carry a literal pipe, or the tools that slice blocks out of the
# issue would find a delimiter inside the payload they are slicing on.
NOT_CELL = "[^" + V + "]{0,40}"
OPTIONAL_CLAIM = re.compile(
    "ENV" + NOT_CELL + "(optional|defaults?" + "[[:space:]]+(to[[:space:]]+)?"
    + "[\"']?development)", re.I)

claim = 0
for text in (readme, deploy):
    for ln in text.splitlines():
        if OPTIONAL_CLAIM.search(ln):
            claim += 1
print("DOCS_DEFAULT_CLAIM_COUNT: %d" % claim, flush=True)
