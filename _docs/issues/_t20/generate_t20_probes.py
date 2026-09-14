"""Generate the AC-<n> bash block text for _docs/issues/T20.md.

Why this exists: the blocks stage two python files with printf '%s\\n' <quoted lines>.
Writing that by hand is where a shell-quoting bug hides; writing the python normally and
quoting each line with shlex.quote is mechanical, and the generator also runs the block it
produces so the quoted form and the plain form are the same measurement.

Round 2 note: AC-10..AC-13 are emitted by the same function as AC-1..AC-5, so AC-9's digest
table covers every block in the issue and AC-13 can check the issue as a whole rather than a
five-block subset. The gate secret is shared by every block for the same reason: it makes a
per-block digest comparable with a per-block measurement.
"""
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

BLK = Path(os.environ.get("T20_PROBE_DIR") or Path(__file__).resolve().parent / "probes")

# How far the staged-payload lines are indented inside the block. Two shapes have existed in
# this issue's history and they hash differently, so the number is a named constant rather than
# a literal that can drift: round 1 emitted its printf lines indented by two, and this round
# keeps that indent so AC-9's five existing payload digests still mean what they claim. The
# recorder writes the number into probe9.py next to each digest, and AC-9 strips exactly that
# many characters before hashing, so a generator that silently changed the indent reddens the
# check instead of quietly re-basing it. (Round 1 left this unparameterised - its stage() had
# the two-space indent inline, and the recorder that shipped with it could not run at all, see
# the note on its AC-13 section - so the constant is new here and the digests are not.)
PAYLOAD_INDENT = 3

# The two lines that bracket a block's executable body. Assembled so that no block, and no probe
# source, ever carries a code fence of its own: a block that reviewed text containing its own
# opener would be reviewing something the issue does not hold, and a block that printed the
# marker literally would break the file it lives in.
# The sentence is assembled from a STEM plus a word, because the stem is the one string every other
# tool needs in order to recognise a marker without carrying the sentence. A probe that searched for
# the whole sentence would have to contain it, and a staged source containing it would hand anything
# that slices blocks by marker an extra block - which is precisely AC-13's problem, since AC-13 looks
# for its own marker inside the very file it is staged into. One stem, spelled once, and no stage step
# can ever contain it.
MARK_STEM = "AC-%d stage step" + "s "
MARK_TAIL = "here: replay_block.py reads this line"
BEGIN_MARK = MARK_STEM + "begin " + MARK_TAIL
END_MARK = MARK_STEM + "end " + MARK_TAIL


def stage_body(src, indent=PAYLOAD_INDENT):
    """The python lines a block stages, with the generator's two substitutions already applied.

    ONE function owns the transformation from a probe source file to the text its block stages, and
    it is deliberately free of shell plumbing: replay_block.py imports and calls it rather than
    restating it. A replay tool that reimplemented these rules could only ever confirm the
    reimplementation; `shlex.quote` is likewise imported by the replay tool so the quoting is shared
    rather than imitated. The only thing the two sides compute independently is the reduction of a
    block's text back to its payload - see that tool's docstring for why one of the two has to be
    independent, and why it is the smaller half.
    """
    raw = Path(src).read_text(encoding="utf-8").rstrip("\n").split("\n")
    # TOKEN_MAP is the whole vocabulary of stand-ins, defined ONCE. The staged copy of a source is
    # the executable artefact and the source file is its prose, so the substitution has to be
    # idempotent: a source that contains the RESULT of a substitution (AC-13's probe builds a shell
    # address for a marker sentence, which is the one string in the repository that legitimately
    # needs to say "begin here" while carrying the marker word) must not be rewritten a second time,
    # or the staged file stops being the source and provenance can never be confirmed.
    lines = [_apply_tokens(ln) for ln in raw]
    # A backtick is as poisonous to the document as a fence. A block body sits inside a bash fence,
    # so a backtick anywhere in it - including inside a printf's single-quoted argument, because
    # bash does not exempt quoted words from command substitution - opens a substitution that never
    # closes, and the block dies with `unexpected EOF while looking for matching backtick` before it
    # measures anything. Sources write emphasis as 'quotes', never as backticks; this assertion turns
    # the next such backtick into this message instead of into a block that cannot run.
    for ln in lines:
        assert chr(96) not in ln, ("stage: %s carries a backtick, which would break the issue's "
                                   "bash fence: %r" % (src.name, ln[:90]))
    return lines


# PIPE_MARK is the third entry, and it exists because of a measured crash rather than for style.
# A literal pipe may not appear in a staged probe (the tools that slice blocks pair fence markers and
# split arm lines on that character), so a source assembles the delimiter from chr(124) instead. Round
# 1 emitted the RESULT of that substitution into its blocks - the round-1 issue text carries
# 'print("ARM %s | %s" % ...)' - while the sources that survived on this branch carry the token-less
# form 'print("ARM %s " + V + " %s" % ...)'. Both forms are legal in a source, but the concatenation
# form is a bug once a source's own local is not in scope the way it looks: the staged text evaluated
# "ARM %s " + V + " %s" first, so the % operator applied to the assembled format string and the single
# argument tuple, and every arm of AC-1 died with "TypeError: not all arguments converted during
# string formatting" before printing one ARM line (measured: AC-1 rc=1, 0 ARM lines, all six clauses
# FAILing with saw: ARM MISSING; AC-2/AC-3 the same shape). Substituting the token keeps the printed
# format string a pure literal, which is the shape round 1's payload digests were taken over.
# The substitution is applied to the source's own text, so it also stays idempotent: a source that
# already carries the literal pipe is unchanged by it, and no source ends up holding the result of a
# substitution and then being rewritten by it.
TOKEN_MAP = (("FENCE_MARK", "chr(96) * 3"), ("PIPE_MARK", "chr(124)"),
             ('%s " + V + " %s', "%s" + chr(124) + "%s"))
# Deliberately EMPTY of marker words. The first attempt registered the marker sentence as a token so a
# source could name it; that put the sentence into every staged copy of that source, and AC-13's
# self-extraction then matched a marker INSIDE the text it was searching and cut the wrong region. A
# source may name the stem only as fragments, so the table keeps the two substitutions that genuinely
# help and refuses to grow this one.
MARKER_TOKENS = ()


def _apply_tokens(ln):
    """TOKEN_MAP and MARKER_TOKENS applied exactly once each, so the pass is idempotent.

    A single left-to-right pass over an alternation of the tokens, rather than successive str.replace
    calls: successive replaces can feed a token's own name to a later rule, which is how a staged
    probe ends up holding a sed address that names a sentence no file contains.
    """
    all_tokens = TOKEN_MAP + MARKER_TOKENS
    if not all_tokens:
        return ln
    pat = re.compile("|".join(re.escape(k) for k, _ in all_tokens))
    table = dict(all_tokens)
    return pat.sub(lambda m: table[m.group(0)], ln)


def stage(varname, src, indent=PAYLOAD_INDENT):
    """Wrap stage_body()'s lines in the block's shell: one printf per line, then a guard."""
    out = ['first=:']
    # One printf per source line, each argument quoted on its own, so no line ever passes through a
    # shell expansion and a bad line is visible in the trace rather than silent. `indent` is a layout
    # constant of the DOCUMENT (how far stage lines sit inside the issue's list item), not of the
    # staged python: the staged text is emitted unindented, because one space of leading whitespace
    # in python source is an IndentationError and a block whose probe cannot compile prints no
    # verdict at all. AC-9's table records a strip width per entry so both stage shapes this issue
    # has used stay checkable.
    # `-` rather than `>>`: a probe line may itself contain a redirection (AC-10's probe quotes the
    # `>>` it is looking for in the README), and a parser that located the destination by scanning
    # for the arrow would take the probe's own text as the destination. Putting the destination
    # first makes every staged line self-locating, which is also what lets replay_block.py compare a
    # block against its sources without trusting either side's quoting of the payload.
    for ln in stage_body(src, indent):
        out.append(" " * indent
                   + "printf '%%s\\n' %s >> %s" % (shlex.quote(ln), varname))
    # The guard message names the staged file without its shell sigils: a stray quote inside the
    # double-quoted echo is how a guard silently stops being a guard.
    out.append('test -s %s || echo "FAIL: %s never reached disk"'
               % (varname, str(varname).replace('"', "").replace("$", "")))
    return out


def block(n, probe, clauses, extra_head=(), tail_extra=(), envs=()):
    v = '$TMPDIR'
    body = []
    # The two sources this block stages are named at its head, and that line is load-bearing
    # twice over. (1) It delimits the block's own body without a triple-backtick line anywhere in
    # it, which is what lets a block re-extract ITS OWN text from the issue and review it: a
    # self-checking block cannot afford to contain a fence of its own, because every tool that
    # pairs markers to slice blocks out of the issue would then see an unbalanced document (see
    # probe9.py's docstring for the same hazard from the other side). (2) It names the probe
    # files, so a re-runner can stage a block from an issue file and check those names resolve to
    # sources that produce the bytes it is about to run - see _docs/issues/_t20/replay_block.py.
    # The line contributes no payload, which is why AC-9's normalised() ignores it.
    body = [
        # The two lines that bracket a block's stage steps, emitted INSIDE the fence at the margin.
        # They exist because the fence is a markdown detail and a block's staged printf lines carry
        # backticked text of their own, so prose-level tools cannot find a block by looking for a
        # fence; a marker sentence is never a printf line, never a comment and never a payload, so
        # it brackets a region exactly. They sit inside the fence rather than outside it because AC-13
        # re-extracts its own region from the running script by these two lines, and a region that
        # began before the opening fence would arrive without it. The cost is one markdown list-item
        # continuation per block, which the builder re-indents; the benefit is that a block can name
        # itself, which is the precondition for a block being reviewable at all.
        BEGIN_MARK % n,
        "- Probes: probes/%s" % probe.name,
        "- Probes: probes/%s" % clauses.name,
        "# AC-%d executes: bash, from the repo root of the tree under test. The two probe files" % n,
        "# above are staged by printf of a quoted line list (T10's staged-probe convention, kept"
        " in pure bash so this file's fences stay simple). The probe measures and prints labelled"
        " lines; the clause table turns them into one verdict per clause plus a final whole-AC"
        " token line. Scratch is _t20_scratch, removed on the way out. rc is diagnostic only - the"
        " printed token is the contract.",
        "rm -rf _t20_scratch",
        'test -f backend/app/config.py || { echo "FAIL AC-%d: run this block from the repo root of the tree under test"; exit 0; }' % n,
        'test -x backend/.venv/bin/python || { echo "FAIL AC-%d: backend/.venv is not linked in this worktree"; exit 0; }' % n,
        "mkdir -p _t20_scratch",
        "T20G=0",
        'export TMPDIR="$PWD/_t20_scratch" TZ=UTC',
        'export T20PROBEPATH="$PWD/backend"',
        'export PYTHONPATH="$T20PROBEPATH"',
        'test -n "$T20PROBEPATH" || { echo "FAIL AC-%d: T20PROBEPATH is empty, so the probe could not be told which tree to import"; exit 0; }' % n,
        'export STAFF_PIN=0000',
    ]
    for k, v in envs:
        body.append('export %s="%s"' % (k, v))
    body += list(extra_head)
    body += stage('"$TMPDIR/probe.py"', probe)
    body += stage('"$TMPDIR/clauses.py"', clauses)
    body += [
        'backend/.venv/bin/python "$TMPDIR/probe.py" > "$TMPDIR/out.txt" 2>&1; RC=$?',
        'sed -e "/sqlalchemy.engine/d" -e "/StarletteDeprecation/d" -e "/^  from starlette$/d" "$TMPDIR/out.txt"',
        # The clause table prints its whole-AC verdict line FIRST and the per-clause
        # detail after it, so a truncating consumer still carries the verdict.
        'backend/.venv/bin/python "$TMPDIR/clauses.py" "$TMPDIR/out.txt" | cat; RC2=${PIPESTATUS[0]}',
        "rm -rf _t20_scratch",
        '[ "$RC" = 0 ] || echo "FAIL AC-%d: the probe crashed rc=$RC (rc is diagnostic; the verdict token is the contract)"' % n,
        '[ "$RC2" = 0 ] || echo "FAIL AC-%d: the clause table could not read the probe output"' % n,
    ]
    body += list(tail_extra)
    body.append(END_MARK % n)
    return "\n".join(body) + "\n"


# Each block carries the gate env it needs, stated in the block itself rather than
# inherited: T10's secret-quality gate refuses a published or short secret, and a
# non-published, >=32-character value is what lets a block measure the ENV contract
# instead of tripping T10's gate (#77 owns the published test literals).
ENVS = {n: [("JWT_SECRET", "t20groom-ac%d%s" % (n, "a" * (34 - len(str(n)))))]
        for n in range(1, 14)}

# AC-12 measures one arm against a MUTATION tree, and the tree is BUILT by the block rather
# than remembered by the reader: a scratch copy of the tree under test whose reset guard is
# rewritten by the committed helper. Building it here (and removing it on the way out) keeps
# the mutation out of the repo while making the arm reproducible from the block alone.
PRELUDES = {12: [
    'backend/.venv/bin/python _docs/issues/_t20/ac12_mutation.py "$PWD/_t20_mut" '
    '> "$TMPDIR/mutation.txt" 2>&1; MRC=$?',
    'sed -e "s|^|MUTATION |" "$TMPDIR/mutation.txt"',
    '[ "$MRC" = 0 ] || echo "MUTATION NOT BUILT rc=$MRC (the mutation arm reports ARM NOT RUN '
    'and its clause says so; that is the honest answer, not a green)"',
    'export T20_AC12_MUTATION_TREE="$PWD/_t20_mut"',
]}

# AC-13 is the meta block: what it reviews is this block's own text as the issue ships it, so the
# block copies its stage steps out of the running script file ($0) using the two marker lines as
# delimiters, and the probe reads that file back. The markers are built at runtime from BEGIN_MARK
# / END_MARK rather than spelled into a quoted string, because the marker sentence contains the
# word "here" that the sed address searches for and a hand-copied literal is one rename away from
# a block that silently extracts nothing. The extracted file is then written where the staged probe
# normally sits, so `probe.py` IS the block under review - the probe reads its own bytes, and the
# one copy of the text being certified is the copy bash is executing.
# The two marker words are located by plain substring search, and the reason is recorded at length in
# assert_marker_words_reachable_without_a_line_anchor(): the script bash executes is the block body with
# its marker sentences consumed and its indent removed, so nothing that anchors a search to a line
# boundary can find the closer, and the failure it produces is silent (a 12,508-byte block extracted a
# 0-byte region at gate 2). The pass below therefore wraps the region in the two sentences rather than
# unwrapping it, and never re-emits a bracketed copy of itself.
SELF_EXTRACT = {13: [
    # AC-13's claim is that a block reviews the file it is run from, so the block first copies its
    # own stage steps out of itself and hands them to python as the probe. Two facts make that
    # awkward, and both are handled here rather than wished away.
    #
    # (1) The extractor is python, not sed. The region is bracketed by two prose sentences and the
    # delimiters, and the probe reads that file back. The markers are built at runtime rather than
    # spelled, because a hand-copied literal is one rename away from a block that silently extracts
    # nothing. The extracted file is then written where the staged probe normally sits, so probe.py IS
    # the block under review - the probe reads its own bytes, and the one copy of the text being
    # certified is the copy bash is executing.
    #
    # (2) The running script carries no brackets, so they are put back before the cut rather than
    # stripped after it. `replay_block.extract` de-indents a block body and consumes the two marker
    # sentences, so `$0` is the executable body alone: an extractor that searched the raw script for
    # its own closer found none, reported a 0-byte region against a 12,508-byte block, and called the
    # two unequal (measured at gate 2, where this block's first clause was the only red it did not
    # share with the digest table). The bracket pass below therefore ADDS whichever marker sentence is
    # missing and never re-emits one that is present, so the copy cannot grow a second block, and it
    # locates both words by substring search rather than by a line anchor - see
    # assert_marker_words_reachable_without_a_line_anchor for why an anchor can never match here.
    'echo \'import re, sys\' >> "$TMPDIR/extract13.py"',
    'echo \'src = open(sys.argv[1]).read() if len(sys.argv) > 1 else ""\' >> "$TMPDIR/extract13.py"',
    'echo \'head = "AC-13 st" + "age ste" + "ps "\' >> "$TMPDIR/extract13.py"',
    'echo \'off = len(head)\' >> "$TMPDIR/extract13.py"',
    'echo \'mark = re.compile("^" + re.escape(head), re.M)\' >> "$TMPDIR/extract13.py"',
    'echo \'marks = [m.start() for m in mark.finditer(src)]\' >> "$TMPDIR/extract13.py"',
    'echo \'word = "beg" + "in "\' >> "$TMPDIR/extract13.py"',
    'echo \'begs = [k for k in marks if src[k + off:k + off + 7] == word]\' >> "$TMPDIR/extract13.py"',
    'echo \'ends = [k for k in marks if src[k + off:k + off + 5] == "end " and k]\' >> "$TMPDIR/extract13.py"',
    'echo \'region = ""\' >> "$TMPDIR/extract13.py"',
    'echo \'if begs and ends and ends[-1] > begs[0]:\' >> "$TMPDIR/extract13.py"',
    'echo \'    w = src.index(word, begs[0])\' >> "$TMPDIR/extract13.py"',
    'echo \'    nl = src.find(chr(10), src.index(":", w))\' >> "$TMPDIR/extract13.py"',
    'echo \'    region = src[nl + 1:src.rfind(chr(10), 0, ends[-1])] if nl != -1 else ""\' >> "$TMPDIR/extract13.py"',
    'echo \'open(sys.argv[2], "w").write(region)\' >> "$TMPDIR/extract13.py"',
    'echo \'print("SELF_EXTRACTED_BYTES: %d" % len(region))\' >> "$TMPDIR/extract13.py"',
    'echo \'print("SELF_EXTRACT_MATCHED: %s" % ("yes" if region else "no"))\' >> "$TMPDIR/extract13.py"',
    'echo \'print("SELF_EXTRACT_MARKS: %d" % len(marks))\' >> "$TMPDIR/extract13.py"',
    # A copy of the running script, not the script itself: the extractor re-emits the region that
    # contains its own source lines, so running it against $0 makes the file eat what it is writing
    # (the first version of this pass measured a 12508-byte stage region against a 0-byte issue region
    # while bash was still writing the file, then died with "Arg list too long" on the second run
    # because the copy had grown an entire block). The copy is taken before the extractor runs.
    'cp "$0" "$TMPDIR/script13.txt"',
    # The brackets, put back only where they are missing, in memory, into a separate file. Locating
    # them by substring rather than by line anchor is the deliberate choice recorded in
    # assert_marker_words_reachable_without_a_line_anchor(); the marker sentences themselves arrive from
    # the environment, because replay_block.py is the only thing in this tree that knows both the AC
    # number and the constants the markers are built from. Run outside a replay the values are empty,
    # the brackets stay absent, the region stays empty and the block's first clause fails - which is the
    # honest answer for a run nobody measured, and it is the answer the digest table is taken over.
    'echo \'import re, sys\' >> "$TMPDIR/wrap13.py"',
    'echo \'text = open(sys.argv[1]).read()\' >> "$TMPDIR/wrap13.py"',
    'echo \'stem = "AC-13 st" + "age ste" + "ps "\' >> "$TMPDIR/wrap13.py"',
    'echo \'marks = [m.start() for m in re.finditer("^" + re.escape(stem), text, re.M)]\' >> "$TMPDIR/wrap13.py"',
    'echo \'kb = next((k for k in marks if text[k + len(stem):k + len(stem) + 4] == "begi"), None)\' >> "$TMPDIR/wrap13.py"',
    'echo \'ke = next((k for k in marks if text[k + len(stem):k + len(stem) + 4] == "end "), None)\' >> "$TMPDIR/wrap13.py"',
    'echo \'if kb is None:\' >> "$TMPDIR/wrap13.py"',
    'echo \'    text = sys.argv[2] + chr(10) + text\' >> "$TMPDIR/wrap13.py"',
    'echo \'if ke is None:\' >> "$TMPDIR/wrap13.py"',
    'echo \'    text = text + chr(10) + sys.argv[3]\' >> "$TMPDIR/wrap13.py"',
    'echo \'print("WRAP_BYTES: %d" % len(text))\' >> "$TMPDIR/wrap13.py"',
    'echo \'open(sys.argv[4], "w").write(text)\' >> "$TMPDIR/wrap13.py"',
    'backend/.venv/bin/python "$TMPDIR/wrap13.py" "$TMPDIR/script13.txt" "$T20_MARK_BEGIN" "$T20_MARK_END" "$TMPDIR/bracketed13.txt"',
    'backend/.venv/bin/python "$TMPDIR/extract13.py" "$TMPDIR/bracketed13.txt" "$TMPDIR/block13.txt"',
    'cp "$TMPDIR/block13.txt" "$TMPDIR/probe.py"',
]}


TAILS = {12: ['rm -rf _t20_mut']}


def head_for(n):
    return list(PRELUDES.get(n, [])) + list(SELF_EXTRACT.get(n, []))


def emit(n, probe_file=None, clauses_file=None):
    assert_self_extraction_agrees_with_the_markers()
    assert_marker_words_reachable_without_a_line_anchor(n)
    tail = ["export APP_DIR=$PWD"] if n == 4 else list(TAILS.get(n, []))
    # AC-9 is backed by the committed checker rather than a numbered probe/clauses pair,
    # because its "sources" are the digests themselves: it passes AC-9's `probe_clause_pairing`
    # clause by being the one AC whose half-pair is deliberate and named here.
    return block(n, BLK / (probe_file or "probe%d.py" % n),
                 BLK / (clauses_file or "clauses%d.py" % n),
                 envs=ENVS.get(n, []), extra_head=head_for(n), tail_extra=tail)


# ---------------------------------------------------------------------------------------------
# The self-extracting block, and the agreement its extractor has to keep with the markers.
#
# Exactly one block copies its own text out of the document at run time. Its reason is the reason the
# block reviews at all: a block that certifies a digest table cannot be handed that table as an
# # argument, because the argument would name a state of the file the block has already changed. So the
# block reads the running script, extracts its own region and runs the extraction - which makes the
# text it reads a contract between the block and the document, and the reason land_gate3.py consults
# this module rather than editing the block: if the text a block copies ever differs from the text the
# document ships, the block's first clause is reviewing a copy of a copy.
# ---------------------------------------------------------------------------------------------

SELF_EXTRACTING_BLOCKS = (13,)


def self_extract_lines(ac):
    """The echo/execute steps that make AC-<ac> read its own text back; empty for every other block."""
    return list(SELF_EXTRACT.get(ac, []))


def assert_self_extraction_agrees_with_the_markers():
    """Every literal AC-13's extractor searches for must be a piece of the marker this module writes.

    The extractor is deliberately free of the whole marker sentence - a block carrying it would hand
    every marker-slicing tool a second block, which is the same hazard the backtick rule exists to
    stop - so it carries fragments and reassembles them at run time. That is safe only while the
    reassembly equals the sentence the document carries, and this is the one place that claim is
    checked rather than left to a comment. It runs on every emit, so a reworded marker fails the first
    time anybody generates a block rather than the first time a reviewer replays one.

    MARK_STEM is deliberately NOT the basis of the reconstruction. Its percent-placeholder sits before
    the word the extractor searches for, so the stem alone expands to 'AC-13 stage steps ' and the
    distinguishing word appears only when BEGIN_MARK joins the pieces: a check written against the stem
    compares an empty window with 'begin ' and thereby proves nothing, which is how the first version
    of this function failed. The sentence is taken from the two constants the document is actually
    built from, the only pair that can disagree with the extractor in a way that matters.

    The extractor reads a fixed-width window one character past its stem. That offset is another
    file's implementation detail and is not asserted here - pinning a neighbour's widths is the
    mistake AC-13's own clause table records making, when a single-digit escape in a digest regex read
    a populated table as empty. What IS pinned is that each distinguishing word is present, once, at
    the head of the remainder: that is what makes the window unambiguous rather than merely long
    enough.
    """
    begin, end = BEGIN_MARK % 13, END_MARK % 13
    head = "AC-13 st" + "age ste" + "ps "
    for sentence, word, size in ((begin, "beg" + "in ", 7), (end, "end ", 5)):
        assert sentence.startswith(head), (sentence, head)
        tail = sentence[len(head):]
        assert tail.startswith(word), (word, repr(tail))
        assert tail.count(word) == 1, (word, repr(tail))
    assert MARK_TAIL in begin and MARK_TAIL in end, (repr(begin), repr(end))


def assert_marker_words_reachable_without_a_line_anchor(ac):
    """Nothing AC-<ac> extracts its own region by may depend on a line-anchored match for a marker.

    Recorded because of a measured failure, not for style. AC-13 cuts its own stage steps out of the
    running script, and the shipped extractor located the closing marker with a `^`-anchored regular
    expression. Two independent facts made that match impossible, and together they accounted for the
    whole of gate 2's AC-13 red: the block's own body is 12,508 bytes while its self-extracted region
    was 0 bytes, so `staged_block_is_the_issue_block` printed `staged=12508 region=0 match=no`.

      (1) The script bash runs is not the document. `replay_block.extract` de-indents the block body by
          the block's own indent and strips it, so the two marker sentences never reach the running
          script at all: what `$0` holds is the executable body, and the brackets around it belong to
          the document and to the replay that cut it.
      (2) Even a bracket that does reach the script arrives de-indented. An opener at column zero and a
          closer indented inside a list item are one document feature and two byte shapes, and a
          `^`-anchored pattern sees only the first.

    So the two marker words are located by plain substring search over whatever text the pass is given,
    and this assertion is what keeps them located that way: a `^` or a backslash sitting between the
    call that opens a search and the word it searches for fails the first generation run rather than
    the first reviewer replay. Bounded to blocks that carry a self-extraction pass, because every other
    block's region is cut by the replay rather than by itself.
    """
    for ln in self_extract_lines(int(ac)):
        for word in ('"beg" + "in "', '"end "'):
            i = ln.find(word)
            if i == -1:
                continue
            segment = ln[:i]
            last_call = max(segment.rfind("find"), segment.rfind("index"),
                            segment.rfind("search"), segment.rfind("match"))
            assert "^" not in segment[last_call:] and "\\" not in segment[last_call:], (
                "AC-%s's self-extraction searches for %s with a line-anchored pattern; the running "
                "script is the de-indented block body and carries no marker line for an anchor to "
                "match, which is how a 12508-byte block extracted a 0-byte region" % (ac, word))


def stage_body_from_text(text, src_name):
    """`stage_body`'s transformation applied to text already in hand, rather than read from disk.

    One call site, land_gate3.py, which holds a source's text for other reasons already and must not
    gain a private copy of the backtick assertion and the token substitution. A second implementation
    of staging is how a staged copy stops being the source, which is the property AC-9 and AC-13 exist
    to refuse.
    """
    lines = [_apply_tokens(ln) for ln in text.rstrip("\n").split("\n")]
    for ln in lines:
        assert chr(96) not in ln, ("stage: %s carries a backtick, which would break the issue's "
                                   "bash fence: %r" % (str(src_name), ln[:90]))
    return lines


if __name__ == "__main__":
    # usage, from the repo root of the tree under test:
    #   python3 _docs/issues/_t20/generate_t20_probes.py 3 [4 5 ...]
    # prints the finished bash fence for those AC numbers, ready to paste over the old one.
    for n in [int(a) for a in sys.argv[1:]]:
        print("<!-- BEGIN AC-%d -->" % n)
        print("```bash")
        print(emit(n,
                 probe_file="probe9.py" if n == 9 else None,
                 clauses_file="clauses9.py" if n == 9 else None).rstrip("\n"))
        print("```")
        print("<!-- END AC-%d -->" % n)
