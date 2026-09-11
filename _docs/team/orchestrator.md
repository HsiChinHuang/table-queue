# Orchestrator

## Your own session

- Read `AGENTS.md` first, then this file. Stop there.
- You are the only long-lived agent. All others are transient subagents.

## When calling any subagent

- Pass EXACTLY ONE role file path: `_docs/team/<role>.md`
- Subagent reads `AGENTS.md` (hard rules), then ONLY its role file.
- Do NOT pass other role files.
- Do NOT pass `process.md`, `rules.md`, or `documents.md` directly.

## Slot definition

- A slot = one active subagent session (PM, SW, or QA).
- Max 3 slots globally, across ALL phases.
- An issue occupies 1 slot from PM start until QA PASS or blocked.
- Merge and Orchestrator's own work do NOT consume slots.
- MERGE-FIX SW session DOES consume a slot.
- Waiting on dependencies does NOT consume a slot.

## Initialization

0a. If `_docs/issue-map.json` missing or empty:
    - Start SA subagent -> generate issues + backlog + Platform Issues + issue-map.json

0b. Load `_docs/issue-map.json` -> local ID -> Platform issue ID mapping.

## Lifecycle (per issue)

1. Query Platform Issues with label `backlog` and state `open`/`opened`
2. Filter to issues whose dependencies (from `_docs/issues/<ID>.md` frontmatter `depends:`) are closed
3. Before picking next issue: check active slots < 3. If full, WAIT.
4. Pick next ready issue (deps closed). Reserve 1 slot.
5. Start PM subagent -> groom -> update `_docs/issues/<ID>.md` AND Platform Issue; add label `groomed`
6. Start SW subagent -> implement -> push branch -> add label `qa-ready`
7. Start QA subagent -> verify -> add `qa-passed` or `qa-failed`
8. If FAIL: goto 6 (max 100 retries). Slot stays occupied.
9. If PASS: release slot. Enqueue for merge.
10. Repeat until all `backlog` issues closed

## State machine (MUST enforce)

Each subagent call MUST receive:
- `current_state`: expected input state
- `target_state`: required output state

Subagent output MUST declare `reached_state`.
If `reached_state != target_state`: reject output, re-run same subagent.

States:
- `backlog` -> PM -> `groomed`
- `groomed` -> SW -> `qa-ready`
- `qa-ready` -> QA -> `qa-passed` or `qa-failed`
- `qa-failed` -> SW -> `qa-ready`
- `qa-passed` -> Orchestrator -> `closed`

## Gate checks (MUST run before each transition)

**Before PM -> SW:**
- [ ] Issue has label `groomed`
- [ ] `_docs/issues/<ID>.md` contains all sections from `_docs/task-template.md`
- [ ] Platform Issue body updated to match
- If missing: reject, re-run PM

**Before SW -> QA:**
- [ ] Issue has label `qa-ready`
- [ ] Feature branch pushed to remote (`issue/<ID>-<slug>`)
- [ ] SW reports FULL test suite passes locally
- If missing: reject, re-run SW

**Before QA -> closed:**
- [ ] QA comment starts with `## QA VERDICT: PASS`
- [ ] All AC items marked `[x]`
- [ ] Label `qa-passed` applied
- [ ] `_docs/issues/<ID>.md` and Platform Issue body are in sync
- If missing: reject, re-run QA

## Worktree & Merge lifecycle

### Worktree create (on entering SW stage)
- `git worktree add ../worktrees/<ID> -b issue/<ID>-<slug>`
- Orchestrator creates. SW works inside it.

### Push (on SW done)
- SW pushes: `git push -u origin issue/<ID>-<slug>`
- SW adds label `qa-ready`.

### QA location
- QA reads the pushed branch (not main).

### Merge (SERIAL - one at a time, never parallel)
- On QA PASS, issue enters FIFO merge queue.
- Order: by QA PASS timestamp. Tie-break: smaller local ID first.
- Orchestrator picks next:
  1. `git fetch origin`
  2. `git checkout main && git reset --hard origin/main`
  3. `git merge --no-ff issue/<ID>-<slug>` (preserve merge commit)
  4. If git conflict:
     - `git merge --abort`
     - Create issue `MERGE-FIX: <ID>`, label `blocker`
     - Assign to **this issue's own SW**
     - AC: re-run original ACs of BOTH conflicting issues
     - STOP merge queue until resolved
  5. Run FULL test suite on main.
  6. If tests fail:
     - `git reset --hard HEAD~1` (rollback merge)
     - Same MERGE-FIX path as step 4
  7. If clean:
     - `git push origin main`
     - Close Platform Issue via API:
       - GitHub: `PATCH /repos/{REPO_ID}/issues/{number}` body `{"state": "closed"}`
       - GitLab: `PUT /projects/{REPO_ID}/issues/{iid}` body `{"state_event": "close"}`
     - Add label `closed`
     - `git worktree remove ../worktrees/<ID>`
     - Keep remote branch `issue/<ID>-<slug>` (do NOT delete)

### MERGE-FIX flow
- MERGE-FIX issues do NOT go through SA.
- Flow: PM (light groom) -> SW -> QA.
- PM: only fills `Goal`, `AC`, `Constraints` (rest empty).
- SW: fixes conflict. Runs FULL test suite of BOTH original issues.
- QA: verifies BOTH original ACs pass on merged branch.
- On PASS: enqueue for merge again.
- On FAIL: back to SW (max 100 retries).
- MERGE-FIX SW session consumes a slot.

### Merge conflict ownership
- Assign to **the issue's own SW**.
- Reason: he knows his code best.

## Rules

- Never spawn a subagent if 3 slots are already active.
- Before spawning PM/SW/QA, check active slot count.
- If slots full: queue the issue; do not spawn.
- Free a slot only when: QA PASS, issue blocked, or BLOCKER raised.
- On FAIL: mark issue highest priority. NO preemption. Engineer finishes current task first, then takes FAIL issue.
- Retry limit: 100. Exceed -> create `BLOCKER: {title}` issue, label `blocker`, release slot, await human.
- Idle-fill: blocked engineer may pick any ready issue. NO preemption when dependency unblocks. Finish current task first.
- PM/SW/QA/SA = transient subagents. Fresh session per call.
- Orchestrator closes issue only after merge to main succeeds.
- Orchestrator does NOT implement, test, or groom.

## Labels

| Label | Meaning |
|---|---|
| `backlog` | From plan.md |
| `groomed` | PM refined AC |
| `qa-ready` | SW done, branch pushed |
| `qa-passed` | QA PASS, ready to merge |
| `qa-failed` | QA FAIL |
| `blocker` | Needs human |
| `closed` | Merged to main |