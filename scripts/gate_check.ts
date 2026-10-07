// scripts/gate_check.ts
// CLI entry for gate checks.
// Usage: npx tsx scripts/gate_check.ts <role> <phase> <handoff_path> <current_state>

import * as fs from 'fs';
import { runGate } from '../extensions/gate_checker.js';
import type { Handoff, IssueState } from '../extensions/state_machine.js';

const VALID_HANDOFF_ROLES = ['definer', 'builder', 'verifier'] as const;
type HandoffRole = (typeof VALID_HANDOFF_ROLES)[number];

const VALID_PHASES = [
  'survey',
  'review_plan',
  'groom',
  're_groom',
  'implement',
  'fix_qa',
  'fix_merge',
  'fix_regression',
  'verify_issue',
  'verify_pre_merge',
  'verify_post_merge',
] as const;
type HandoffPhase = (typeof VALID_PHASES)[number];

const VALID_STATES = ['defined', 'groomed', 'built', 'verified', 'closed'] as const;
type HandoffState = (typeof VALID_STATES)[number];

function usage(): never {
  console.error('Usage: gate_check.ts <role> <phase> <handoff_path> <current_state>');
  console.error(`  role:          ${VALID_HANDOFF_ROLES.join(' | ')}`);
  console.error(`  phase:         ${VALID_PHASES.join(' | ')}`);
  console.error('  handoff_path:  path to handoff JSON');
  console.error(`  current_state: ${VALID_STATES.join(' | ')} | null`);
  process.exit(2);
}

function isHandoffRole(value: string): value is HandoffRole {
  return (VALID_HANDOFF_ROLES as readonly string[]).includes(value);
}

function isHandoffPhase(value: string): value is HandoffPhase {
  return (VALID_PHASES as readonly string[]).includes(value);
}

function isHandoffState(value: string): value is HandoffState {
  return (VALID_STATES as readonly string[]).includes(value);
}

function main(): void {
  const args = process.argv.slice(2);
  if (args.length !== 4) {
    usage();
  }

  const roleArg = args[0];
  const phaseArg = args[1];
  const handoffPath = args[2];
  const currentStateArg = args[3];

  if (
    roleArg === undefined ||
    phaseArg === undefined ||
    handoffPath === undefined ||
    currentStateArg === undefined
  ) {
    usage();
  }

  // 1. Validate role
  if (!isHandoffRole(roleArg)) {
    console.error(`Invalid role: "${roleArg}". Expected one of: ${VALID_HANDOFF_ROLES.join(', ')}`);
    process.exit(2);
  }
  const role: HandoffRole = roleArg;

  // 2. Validate phase
  if (!isHandoffPhase(phaseArg)) {
    console.error(`Invalid phase: "${phaseArg}". Expected one of: ${VALID_PHASES.join(', ')}`);
    process.exit(2);
  }
  const phase: HandoffPhase = phaseArg;

  // 3. Validate current_state
  let state: IssueState | null;
  if (currentStateArg === 'null') {
    state = null;
  } else if (isHandoffState(currentStateArg)) {
    state = currentStateArg;
  } else {
    console.error(
      `Invalid current_state: "${currentStateArg}". Expected one of: ${VALID_STATES.join(', ')}, null`
    );
    process.exit(2);
  }

  // 4. Read handoff
  if (!fs.existsSync(handoffPath)) {
    console.error(`Handoff not found: ${handoffPath}`);
    process.exit(1);
  }
  const handoff = JSON.parse(fs.readFileSync(handoffPath, 'utf-8')) as Handoff;

  // 5. Cross-check CLI args against handoff (authoritative = handoff; mismatch is a hard error)
  if (handoff.role !== role) {
    console.error(`Role mismatch: CLI="${role}", handoff="${handoff.role}"`);
    process.exit(1);
  }
  if (handoff.phase !== phase) {
    console.error(`Phase mismatch: CLI="${phase}", handoff="${handoff.phase}"`);
    process.exit(1);
  }

  // 6. Run gate
  const result = runGate(handoff, state);
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.passed ? 0 : 1);
}

main();