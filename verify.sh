#!/bin/bash
# verify.sh - Pre-deployment verification for agent team system
# Usage: bash verify.sh
# Exit: 0 = OK, 1 = errors found

set -o pipefail

ERRORS=0
WARNINGS=0

err() { echo "[ERROR] $1"; ERRORS=$((ERRORS+1)); }
warn() { echo "[WARN]  $1"; WARNINGS=$((WARNINGS+1)); }
ok() { echo "[OK]    $1"; }

echo "=== 1. File existence ==="
REQUIRED=(
  "AGENTS.md"
  ".env.example"
  "_docs/SETUP.md"
  "_docs/rules.md"
  "_docs/commands.md"
  "_docs/task-template.md"
  "_docs/testing-guidelines.md"
  "_docs/config.md"
  "_docs/config.yaml.example"
  "_docs/config-migrations.md"
  "_docs/requirements.md.example"
  "_docs/plan.md.example"
  "_docs/team/_shared.md"
  "_docs/team/sa.md"
  "_docs/team/sa-dag.md"
  "_docs/team/pm.md"
  "_docs/team/sw.md"
  "_docs/team/qa.md"
  "_docs/team/orchestrator.md"
  "_docs/team/orchestrator-preflight.md"
  "_docs/team/orchestrator-gates.md"
  "_docs/team/orchestrator-merge.md"
  "_docs/team/orchestrator-rollback.md"
  "_docs/team/orchestrator-labels.md"
  "_docs/team/orchestrator-git.md"
  "_docs/team/orchestrator-human.md"
  "_docs/team/orchestrator-special.md"
  "_docs/team/orchestrator-logging.md"
  "_docs/team/orchestrator-slots.md"
  "_docs/team/orchestrator-authority.md"
  "_docs/team/orchestrator-boundaries.md"
  "_docs/team/orchestrator-failures.md"
)
for f in "${REQUIRED[@]}"; do
  if [ -f "$f" ]; then
    ok "$f"
  else
    err "MISSING: $f"
  fi
done

echo
echo "=== 2. Encoding check (no non-ASCII artifacts) ==="
if grep -rn "§\|⟦\|⟧\|Â\|搂\|┬" _docs/ AGENTS.md 2>/dev/null; then
  err "Encoding artifacts found (see above)"
else
  ok "No encoding artifacts"
fi

echo
echo "=== 3. Reference integrity (static _docs/... refs) ==="
REFS=$(grep -rhoE "_docs/[a-zA-Z0-9/_.-]+\.md" _docs/ AGENTS.md 2>/dev/null | sort -u)
BROKEN=0
while read -r ref; do
  [ -z "$ref" ] && continue
  if [ ! -f "$ref" ]; then
    err "BROKEN REF: $ref"
    BROKEN=$((BROKEN+1))
  fi
done <<< "$REFS"
[ $BROKEN -eq 0 ] && ok "All static references resolve"

echo
echo "=== 4. Directory structure ==="
DIRS=(
  "_docs/team/details"
  "_docs/memory"
  "_docs/memory/candidates"
  "_docs/memory/verified"
  "_docs/issues"
  "_docs/issues/pending"
  "_docs/issues/closed"
  "_docs/log"
  "_docs/state"
)
for d in "${DIRS[@]}"; do
  if [ -d "$d" ]; then
    ok "DIR: $d"
  else
    warn "MISSING DIR: $d (will be created at runtime)"
  fi
done

echo
echo "=== 5. State init files ==="
STATE_FILES=(
  "_docs/state/snapshot.json"
  "_docs/state/retry.json"
  "_docs/state/retry-subagent.json"
  "_docs/state/seq.txt"
  "_docs/state/last-restart.txt"
  "_docs/state/STATUS.md"
  "_docs/state/APPROVALS.md"
  "_docs/state/CONFIG_SNAPSHOT.json"
)
for f in "${STATE_FILES[@]}"; do
  if [ -f "$f" ]; then
    ok "$f"
  else
    warn "MISSING (will be created): $f"
  fi
done

echo
echo "=== 6. Environment variables ==="
[ -f ".env" ] && ok ".env exists" || warn ".env not found"
[ -n "$PLATFORM" ] && ok "PLATFORM=$PLATFORM" || warn "PLATFORM not set in shell"
[ -n "$REPO_ID" ] && ok "REPO_ID=$REPO_ID" || warn "REPO_ID not set in shell"
[ -n "$API_TOKEN" ] && ok "API_TOKEN set" || warn "API_TOKEN not set in shell"

echo
echo "=== 7. Sec. references ==="
SEC_COUNT=$(grep -rc "Sec\. " _docs/team/ 2>/dev/null | awk -F: '{sum+=$2} END {print sum+0}')
ok "$SEC_COUNT Sec. references found"

echo
echo "=== 8. Config keys (informational) ==="
grep -oE "^[a-z_]+:" _docs/config.yaml.example | sort -u | wc -l | xargs echo "Top-level config keys:"

echo
echo "=== Summary ==="
echo "Errors:   $ERRORS"
echo "Warnings: $WARNINGS"
if [ $ERRORS -gt 0 ]; then
  echo "FAIL"
  exit 1
else
  echo "OK"
  exit 0
fi