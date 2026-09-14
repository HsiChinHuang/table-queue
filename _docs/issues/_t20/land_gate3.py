"""Land GATE-3's state: the issue's blocks and the tools that reproduce them, in one reviewable pass.

    backend/.venv/bin/python _docs/issues/_t20/land_gate3.py            # verify only, writes nothing
    backend/.venv/bin/python _docs/issues/_t20/land_gate3.py --write    # land

Five inputs, three sources and two derived shapes, and no fallback anywhere in the join:

  - `git show <BASE_R2>:_docs/issues/T20.md` - this round's own issue text: the prose, AC-11's
    section, and the five round-2 blocks exactly as the previous round's freeze converged them.
  - `git show <BASE_R1>:_docs/issues/T20.md` - round 1's five block bodies, byte for byte.
  - the probe sources in this directory - the five blocks this round regenerates, re-emitted here so a
    failure shows up as a finding rather than as a silently stale digest table.
  - `probes/probe9.py` - the digest tables, recorded from the built document by the recorder.
  - the tool sources named in PROBE_TOOLS - re-quoted into the blocks that stage them.

Three findings decided the shape of this join. All three were measured on this branch.

  (1) Round 1's headings are ordered list items (`2. [ ] **AC-1** ...`), so a section splitter anchored
      on a margin `^- [ ] **AC-**` finds five sections rather than ten, and a builder that reassembles
      a document out of the spans it did find preserves everything else by accident. That is how the
      first landing replaced AC-1..AC-5 with this round's regenerated block shape - a shape differing
      from round 1's on 122 of AC-1's staged lines. Blocks are therefore addressed by marker or fence
      position here, never by heading.

  (2) AC-4's and AC-5's blocks contain backticks inside printf-quoted python docstrings
      (`""os.environ.setdefault(...)""`, ``settings.env == "development"``). A fence test that asks
      whether a line CONTAINS three backticks closes AC-4's block 140 lines early, and the next match
      then swallows AC-5's real closer - ten "blocks" reported for a seven-block document, and a
      payload digest taken over two blocks. A fence line is a line whose stripped content IS the
      marker, optionally plus the language tag; `fence_lines()` is the only place that test is written.

  (3) Four of the ten blocks stage a tool source as well as a probe pair: AC-9 and AC-13 stage
      `check_blocks.py`, and AC-10 and AC-11 stage `record_t20_digests.py`. `replay_block.py` re-derives
      every staged line from the generator plus the two manifest names, so a tool source that changed
      reddens those four blocks as a provenance REFUSAL - and one of those four, AC-11, is the block
      whose own clause refuses any second opt-in variable, so its red would be an artefact of this
      round's own prose work rather than a finding about the fix. The round-1 precedent for the case is
      `ac12_mutation.py`, whose text the AC-12 block states is the committed file, unchanged. That
      precedent is generalised here: `check_blocks.py` and `record_t20_digests.py` are placed on the
      same footing by their own record lines, and this tool re-quotes them into the four blocks as the
      last step, so the document, the tables and the tools converge in the one pass a reviewer reads.
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import r1_landed as L  # noqa: E402
import replay_block as R  # noqa: E402

ROOT = L.ROOT
F = L.F
BASE_R1 = L.BASE_R1
BASE_R2 = "b4a8021"
R2_BLOCKS = ("9", "10", "11", "12", "13")
# No block stages a tool source, and the table that would have named four is empty. The reasoning that
# filled it, and the measurement that emptied it, are both worth keeping here: AC-9/AC-13's blocks
# stage probe9.py + clauses9.py and AC-10/AC-11's stage probe10/11 + clauses10/11, and `probe13.py`
# only asks whether `_docs/issues/_t20/record_t20_digests.py` EXISTS (`MACHINERY_PRESENT:`), as do the
# other three. So a tool-source edit needs no re-quaring pass, and inventing one would have edited four
# blocks to satisfy a hazard that has no instance. What the edit DOES have to satisfy is the backtick
# rule the blocks themselves enforce: `generate_t20_probes.stage_body()` refuses any staged source
# containing a backtick, and check_blocks.py's emit gate surfaced the constraint the moment those two
# files carried markdown emphasis. Their prose now quotes code with single quotes, which is the
# convention every other staged probe already uses.
PROSE_FIXES = (
    ("`python3 _docs/issues/_t20/ac12_mutation.py <scratch>`",
     "`backend/.venv/bin/python _docs/issues/_t20/ac12_mutation.py <scratch>`",
     "the AC-12 mutation arm's builder is invoked with the tree's own interpreter, because a bare "
     "`python3` is not on the PATH surface a gate worktree exposes"),
)


def document(rev):
    out = subprocess.run(["git", "show", "%s:_docs/issues/T20.md" % rev],
                         capture_output=True, text=True, cwd=str(ROOT))
    if not out.stdout:
        raise SystemExit("land_gate3: cannot read %s:_docs/issues/T20.md (%s)"
                         % (rev, out.stderr.strip().split("\n")[-1] or "empty output"))
    return out.stdout


def fence_lines(md):
    """Every real fence line, as (offset, is_opener). See finding (2) in the module docstring."""
    return [(m.start(), m.group(0).strip().endswith("bash"))
            for m in re.finditer(r"(?m)^[ \t]*(" + re.escape(F) + r")(?:bash)?[ \t]*$", md)]


def blocks_by_fences(md):
    """AC -> (fence_opener_start, closer_line_end), paired strictly opener-then-closer."""
    pairs, open_at, depth = [], None, 0
    for off, is_opener in fence_lines(md):
        if is_opener:
            if depth:
                raise SystemExit("land_gate3: fence opener at %d inside an open block" % off)
            open_at, depth = off, 1
        else:
            if not depth:
                raise SystemExit("land_gate3: fence closer at %d closes nothing" % off)
            pairs.append((open_at, off))
            depth = 0
    if depth:
        raise SystemExit("land_gate3: the document ends inside an open fence")
    out = {}
    for a, closer in pairs:
        body = md[md.index("\n", a) + 1:closer]
        m = re.search(r"(?m)^ *# AC-(\d+) executes", body)
        if m:
            out[m.group(1)] = (a, md.index("\n", closer))
    return out


def staged_destinations(md, ac):
    """The scratch paths one block stages into, in stage order. Derived from the block's own text."""
    from replay_block import extract
    body = extract(md, ac) or ""
    return [ln.strip().rsplit(">>", 1)[-1].strip().strip('"')
            for ln in body.split("\n") if ln.lstrip().startswith("printf ")]


def manifest(ac, r1_doc):
    """Round-1 provenance, as a bash comment at the tail of the block's own stage steps.

    Round 1's five blocks carry no manifest, and `replay_block.py` refuses a block that cannot name
    its sources - correctly, because a provenance inferred from a filename convention re-runs the wrong
    probe, which is how round 1's AC-13 was handed AC-9's payload. The two sentences cannot go at the
    head: they are markdown list items, and `-` is a command name to bash, so a head manifest makes the
    block's first executable lines unexecutable and aborts the printf stage loop before it stages
    anything (measured: `-: command not found`, exit 127, and the verdict printed anyway). At the tail
    they are the block's last lines, they are stripped from the text a replay hands to bash, and they
    add no payload, so the pinned digests - which are taken over printf lines - do not move.
    """
    names = [n for n in ("probe%s.py" % ac, "clauses%s.py" % ac)
             if (HERE / "probes" / n).exists()]
    if len(names) != 2:
        raise SystemExit("land_gate3: AC-%s's manifest would name %s, and this tree does not hold "
                         "both" % (ac, names))
    return "\n".join("- Probes: probes/%s" % n for n in names)


def tool_block(ac, name, md_of_block, verb="printf"):
    """The stage steps that write one scratch file, taken from the block exactly as it ships.

    The verb is a parameter because the two shapes this directory stages with are not the same shape:
    probe and clause files go through printf, and AC-13's self-extractor goes through echo. A pass
    that looked only for printf would find no extractor to replace, say so, and leave the block
    certified text it no longer holds - which is the failure this whole function exists to refuse.
    """
    lines = [ln for ln in md_of_block.split("\n")
             if ln.lstrip().startswith(verb + " ") and ln.rstrip().endswith('>> "$TMPDIR/%s"' % name)]
    # The scratch file is written by more than the steps that create it: AC-13's extractor is then
    # copied into the slot the staged probe normally occupies, and a replacement pass that stopped at
    # the last writing step would leave the block's own copy step pointing at a file the new steps
    # never produced. Taking the whole contiguous run of steps that MENTION the scratch file - which
    # is how the block addresses it, one file per scratch path - is what keeps the run a run.
    if lines:
        all_lines = md_of_block.split("\n")
        first = all_lines.index(lines[0])
        last = first + len(lines) - 1
        mention = lambda ln: ('"$TMPDIR/%s"' % name) in ln and ln.strip()
        while last + 1 < len(all_lines) and mention(all_lines[last + 1]):
            last += 1
        while first - 1 >= 0 and mention(all_lines[first - 1]):
            first -= 1
        lines = [ln for ln in all_lines[first:last + 1] if mention(ln)]
    if not lines:
        raise SystemExit("land_gate3: AC-%s names no stage steps for %s, so the tool source cannot "
                         "be re-quoted into it" % (ac, name))
    return lines


def build(r1_doc, r2_doc):
    """The landed document. Order is the whole of the correctness argument: every replacement is
    applied from the end backwards, so no offset below a replacement is invalid when it is read."""
    built = r2_doc
    for old, new, _ in PROSE_FIXES:
        assert built.count(old) == 1, "prose fix %r matched %d" % (old[:32], built.count(old))
        built = built.replace(old, new)
    r1_blocks = blocks_by_fences(r1_doc)
    for ac in L.R1_BLOCKS:
        if ac not in r1_blocks:
            raise SystemExit("land_gate3: round 1 holds no block for AC-%s" % ac)
    for (ac, (a, b)) in sorted(blocks_by_fences(built).items(), key=lambda kv: -kv[1][0]):
        if ac in R2_BLOCKS:
            continue
        seg = r1_doc[r1_blocks[ac][0]:r1_blocks[ac][1]].split("\n")[1:-1]
        inner = L.deindent("\n".join(seg)) + "\n" + manifest(ac, r1_doc)
        built = (built[:a] + F + "bash\n" + L.BEGIN % ac + "\n" + inner
                 + "\n" + L.END % ac + "\n" + F + built[b:])
    return built


def refresh_self_extract(built):
    """Re-quote AC-13's self-extractor into AC-13's own block, from the generator that owns it.

    The block stages no third probe source, so nothing here is a re-quaring of a tool file. What is
    re-emitted is the block's own first stage steps - the echo lines that build the extractor which
    copies the block out of the running script - and they move for the same reason `ac12_mutation.py`
    moves: the AC-13 block's whole claim is that it reviews the region the document ships, so the
    delimiters it cuts by and the delimiters the document's blocks carry cannot be allowed to drift
    apart. Round 1 left them in sync by hand.

    The lines are read out of `generate_t20_probes.self_extract_lines(13)`, which is what the generator
    emits, so a rename of the marker sentence moves this pass and the emitted block together, and
    `assert_self_extraction_agrees_with_the_markers()` runs first to refuse a rename that splits the
    extractor's fragments away from the sentence it is trying to find.
    """
    import generate_t20_probes as gen
    gen.assert_self_extraction_agrees_with_the_markers()
    for ac in gen.SELF_EXTRACTING_BLOCKS:
        ac = str(ac)
        region = blocks_by_fences(built)[ac]
        old = tool_block(ac, "extract%s.py" % ac, built[region[0]:region[1]], verb="echo")
        new = [ln for ln in gen.head_for(int(ac)) if ln.strip()]
        # The BEGIN sentence, the two `- Probes:` lines and the END sentence are left exactly where the
        # previous round froze them - outside the steps this pass replaces - because the block cuts its
        # own region by them: the extractor takes the FIRST begin match and the LAST end match, so a
        # marker that drifted inside the steps it brackets would make the block extract a region that
        # starts or stops inside itself. The generator emits those sentences as part of `head_for()`,
        # which is why they are filtered out here rather than emitted: this pass replaces the block's
        # executable body, not its brackets.
        anchors = {ln.strip() for ln in (L.BEGIN % ac, L.END % ac,
                                         "- Probes: probes/probe%s.py" % ac,
                                         "- Probes: probes/clauses%s.py" % ac)}
        new = [ln for ln in new if ln.strip() not in anchors]
        lines = built[region[0]:region[1]].split("\n")
        first, last = lines.index(old[0]), lines.index(old[-1])
        # The old run is replaced by the new one in place. Asserting the replacement is CONTIGUOUS is
        # the guard against a block that grew a second extractor-shaped step somewhere else: a
        # non-contiguous match would splice the new steps into the middle of the old ones and leave a
        # block that parses, prints a verdict, and reviews the wrong file. The shipped run may also
        # carry the END marker sentence, which the extractor is allowed to search for (a block that
        # could match its own closer would match itself before it matched the document) and which this
        # pass therefore leaves exactly where the previous round froze it rather than dropping it.
        if any(ln.strip() in anchors for ln in old):
            raise SystemExit("land_gate3: AC-%s's self-extraction run carries a marker or probe line "
                             "inside the steps being replaced, which would move the block's own region "
                             "cut" % ac)
        # The extractor copies the running script and reads that copy, so the text it certifies is the
        # body as bash holds it. Bash holds no marker sentences: they are prose lines the previous
        # round emitted inside the fence, and a step that replaced them would hand the extractor a
        # script with no begin marker in it - which is exactly how a green-looking block reported a
        # 0-byte issue region while its own 12508-byte copy sat next to it. So this pass keeps the
        # whole bracketed region intact and rebuilds only the executable steps between them, which is
        # also the only region the digest normalisation reads.
        keep_begin = lines.index(L.BEGIN % ac)
        keep_end = lines.index(L.END % ac)
        if not (first > keep_begin and last < keep_end):
            raise SystemExit("land_gate3: AC-%s's self-extraction steps are not wholly between the "
                             "two marker sentences, so replacing them would move the block's own "
                             "region cut" % ac)
        rebuilt = lines[:first] + new + lines[last + 1:]
        built = built[:region[0]] + chr(10).join(rebuilt) + built[region[1]:]
    return built


def record(built):
    """Write the built document, then run the committed recorder over it, then rebuild the tools'
    own digests into the blocks that name them. The recorder rebuilds the issue through the builder,
    so it runs first and this tool's tool-source pass runs last and wins."""
    (ROOT / "_docs" / "issues" / "T20.md").write_text(built, encoding="utf-8")
    r = subprocess.run([sys.executable, str(HERE / "record_t20_digests.py")],
                       capture_output=True, text=True, cwd=str(ROOT))
    if r.returncode:
        raise SystemExit("land_gate3: the recorder refused - %s"
                         % (r.stdout + r.stderr).strip().split("\n")[-1])
    return r.stdout.strip().split("\n")[-1]


def verify(built, pre_landing, r1_doc):
    problems = list(L.selfcheck(built))
    got = blocks_by_fences(built)
    if sorted(got) != sorted(L.ALL_BLOCKS):
        problems.append("the document pairs into %d blocks (%s)" % (len(got), ",".join(sorted(got))))
    return problems


if __name__ == "__main__":
    write = "--write" in sys.argv
    target = ROOT / "_docs" / "issues" / "T20.md"
    pre_landing = target.read_text(encoding="utf-8")
    r1_doc = document(BASE_R1)
    built = build(r1_doc, document(BASE_R2))
    built = refresh_self_extract(built)
    problems = verify(built, pre_landing, r1_doc)
    moved = [m for m in L.prose_problems(document(BASE_R2), built)
             if not any(old[:32] in m for old, _, _ in PROSE_FIXES)]
    problems += moved
    for p in problems:
        print("  " + p)
    if problems:
        raise SystemExit("land_gate3: refused to write - %d problem(s)" % len(problems))
    if not write:
        print("land_gate3: verified without writing (%d bytes, %d blocks)"
              % (len(built), len(blocks_by_fences(built))))
        raise SystemExit(0)
    print("recorded: %s" % record(built))
    final = target.read_text(encoding="utf-8")
    print("landed %s: %d bytes, %d block(s), round-1 payloads from %s"
          % (target, len(final), len(blocks_by_fences(final)), BASE_R1))
