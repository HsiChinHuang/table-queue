// extensions/state_machine.ts
// State machine: define legal states and transitions, validate handoff reached_state

import * as fs from 'fs';

// ============================================================
// State definitions
// ============================================================

export type IssueState =
  | 'defined'
  | 'groomed'
  | 'built'
  | 'verified'
  | 'closed';

export type Role = 'definer' | 'builder' | 'verifier' | 'orchestrator';

export type Phase =
  | 'survey' | 'review_plan' | 'groom' | 're_groom'
  | 'implement' | 'fix_qa' | 'fix_merge' | 'fix_regression'
  | 'verify_issue' | 'verify_pre_merge' | 'verify_post_merge';

// ============================================================
// Transition table
// ============================================================

interface Transition {
  from: IssueState;
  to: IssueState;
  role: Role;
  phases: Phase[];
}

const LEGAL_TRANSITIONS: Transition[] = [
  // === Definer ===

  // review_plan -> defined (review only, no state change)
  { from: 'defined', to: 'defined', role: 'definer', phases: ['review_plan'] },

  // groom -> groomed (refine AC, transition to groomed state)
  { from: 'defined', to: 'groomed', role: 'definer', phases: ['groom'] },

  // re_groom -> groomed (fix AC, return to groomed state)
  { from: 'built', to: 'groomed', role: 'definer', phases: ['re_groom'] },

  // === Builder ===

  // implement -> built (implementation complete)
  { from: 'groomed', to: 'built', role: 'builder', phases: ['implement'] },

  // fix_qa -> built (fix QA failure, stay built)
  { from: 'built', to: 'built', role: 'builder', phases: ['fix_qa'] },

  // fix_merge -> built (resolve merge conflict, stay built)
  { from: 'built', to: 'built', role: 'builder', phases: ['fix_merge'] },

  // fix_regression -> built (fix regression, stay built)
  { from: 'built', to: 'built', role: 'builder', phases: ['fix_regression'] },

  // === Verifier ===

  // verify_issue -> verified (verification passed)
  { from: 'built', to: 'verified', role: 'verifier', phases: ['verify_issue'] },

  // verify_pre_merge -> verified (pre-merge check, no state change)
  { from: 'verified', to: 'verified', role: 'verifier', phases: ['verify_pre_merge'] },

  // verify_post_merge -> verified (post-merge check, no state change)
  { from: 'verified', to: 'verified', role: 'verifier', phases: ['verify_post_merge'] },
];

// ============================================================
// Handoff interface
// ============================================================

export interface Handoff {
  schema_version: string;
  issue_id: string;
  role: Role;
  phase: Phase;
  status: 'COMPLETE' | 'FAIL' | 'BLOCKER';
  reached_state: IssueState | 'unchanged';
  evidence: Record<string, unknown>;
  artifacts: {
    files_written: string[];
    platform_issue: number | null;
    output_path: string;
  };
  error: ErrorPayload | null;
  next_action: NextAction | null;
  timestamp: string;
  retry_count: number;
}

export interface ErrorPayload {
  error_type: string;
  error_code: string;
  message: string;
  context: Record<string, unknown>;
  retryable: boolean;
  suggested_action: string;
  suggested_role?: string | null;
  suggested_phase?: string | null;
}

export interface NextAction {
  role: Role;
  phase: Phase;
  reason: string;
}

// ============================================================
// Validation result
// ============================================================

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

// ============================================================
// Core validation logic
// ============================================================

const BUSINESS_FAILURE_TYPES = [
  'implementation',
  'ac_ambiguous',
  'ac_wrong',
  'test_env',
  'test_quality',
  'merge_conflict',
  'regression',
] as const;

/**
 * Validate the handoff state transition.
 * The `survey` phase is special: it creates a new issue, not a state
 * transition. It is exempt from transition checks.
 *
 * @param handoff - The handoff JSON written by the subagent
 * @param currentState - Current state of the issue (null for brand-new issues)
 * @returns Validation result
 */
export function validateTransition(
  handoff: Handoff,
  currentState: IssueState | null
): ValidationResult {
  const errors: string[] = [];

  // 1. Validate role + phase combination
  const phaseValid = isValidPhaseForRole(handoff.role, handoff.phase);
  if (!phaseValid) {
    errors.push(
      `Invalid phase "${handoff.phase}" for role "${handoff.role}"`
    );
  }

  // 2. Validate reached_state consistency with status
  const stateConsistency = validateStateConsistency(handoff);
  if (!stateConsistency.valid) {
    errors.push(...stateConsistency.errors);
  }

  // 3. Validate transition legality
  // Exception: `survey` is exempt because it creates a new issue.
  if (handoff.status === 'COMPLETE' && handoff.phase !== 'survey') {
    if (currentState === null) {
      errors.push(
        `currentState is null but phase is "${handoff.phase}" (only survey may create new issues)`
      );
    } else {
      const transitionValid = isLegalTransition(
        currentState,
        handoff.reached_state as IssueState,
        handoff.role,
        handoff.phase
      );
      if (!transitionValid) {
        errors.push(
          `Illegal transition: ${currentState} -> ${handoff.reached_state} ` +
          `by ${handoff.role}:${handoff.phase}`
        );
      }
    }
  }

  // 4. Validate error field
  if (handoff.status !== 'COMPLETE' && !handoff.error) {
    errors.push(`status is ${handoff.status} but error is null`);
  }
  if (handoff.status === 'COMPLETE' && handoff.error) {
    errors.push(`status is COMPLETE but error is not null`);
  }

  // 5. Validate next_action
  if (handoff.status === 'FAIL' && !handoff.next_action) {
    errors.push(`status is FAIL but next_action is null`);
  }
  if (handoff.status !== 'FAIL' && handoff.next_action) {
    errors.push(`status is ${handoff.status} but next_action is not null`);
  }

  // 6. Cross-validate failure_type consistency (verifier: verify_issue, status FAIL)
  if (
    handoff.role === 'verifier' &&
    handoff.phase === 'verify_issue' &&
    handoff.status === 'FAIL'
  ) {
    const ev = handoff.evidence;
    const evFailureType = ev['failure_type'];
    const ctx = handoff.error?.context ?? {};
    const ctxFailureType = ctx['failure_type'];

    if (typeof evFailureType !== 'string') {
      errors.push('evidence.failure_type is required on verifier FAIL');
    } else if (!BUSINESS_FAILURE_TYPES.includes(evFailureType as typeof BUSINESS_FAILURE_TYPES[number])) {
      errors.push(`evidence.failure_type is not a legal business failure type: ${evFailureType}`);
    }

    if (typeof ctxFailureType !== 'string') {
      errors.push('error.context.failure_type is required on verifier FAIL');
    } else if (ctxFailureType !== evFailureType) {
      errors.push(
        `failure_type mismatch: evidence="${String(evFailureType)}", error.context="${ctxFailureType}"`
      );
    }

    if (handoff.error && handoff.error.error_type !== 'business_failure') {
      errors.push(
        `verifier FAIL requires error.error_type=business_failure, got "${handoff.error.error_type}"`
      );
    }
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Validate role + phase combination.
 */
function isValidPhaseForRole(role: Role, phase: Phase): boolean {
  const rolePhases: Record<Role, Phase[]> = {
    definer: ['survey', 'review_plan', 'groom', 're_groom'],
    builder: ['implement', 'fix_qa', 'fix_merge', 'fix_regression'],
    verifier: ['verify_issue', 'verify_pre_merge', 'verify_post_merge'],
    orchestrator: [],
  };
  return rolePhases[role]?.includes(phase) ?? false;
}

/**
 * Validate reached_state consistency with status.
 */
function validateStateConsistency(handoff: Handoff): ValidationResult {
  const errors: string[] = [];

  if (handoff.status === 'COMPLETE') {
    if (handoff.reached_state === 'unchanged') {
      errors.push(
        `status is COMPLETE but reached_state is "unchanged"`
      );
    }
  } else {
    if (handoff.reached_state !== 'unchanged') {
      errors.push(
        `status is ${handoff.status} but reached_state is "${handoff.reached_state}" ` +
        `(expected "unchanged")`
      );
    }
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Check whether a transition is legal.
 */
function isLegalTransition(
  from: IssueState,
  to: IssueState,
  role: Role,
  phase: Phase
): boolean {
  return LEGAL_TRANSITIONS.some(
    (t) =>
      t.from === from &&
      t.to === to &&
      t.role === role &&
      t.phases.includes(phase)
  );
}

// ============================================================
// Load handoff from file
// ============================================================

export function loadHandoff(filePath: string): Handoff | null {
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(content) as Handoff;
  } catch (err) {
    console.error(`Failed to load handoff from ${filePath}`, err);
    return null;
  }
}

// ============================================================
// Convenience: validate and return
// ============================================================

export function validateHandoffFile(
  filePath: string,
  currentState: IssueState | null
): ValidationResult {
  const handoff = loadHandoff(filePath);
  if (!handoff) {
    return {
      valid: false,
      errors: [`Failed to load handoff from ${filePath}`],
    };
  }
  return validateTransition(handoff, currentState);
}

// ============================================================
// State transition helper
// ============================================================

/**
 * Get the next role and phase for a given state.
 */
export function getNextRoleAndPhase(
  state: IssueState,
  context: {
    groomed: boolean;
    verifier_failed: boolean;
    merge_conflict: boolean;
    regression: boolean;
  }
): { role: Role; phase: Phase } | null {
  switch (state) {
    case 'defined':
      return context.groomed
        ? { role: 'builder', phase: 'implement' }
        : { role: 'definer', phase: 'groom' };

    case 'groomed':
      return { role: 'builder', phase: 'implement' };

    case 'built':
      if (context.merge_conflict) {
        return { role: 'builder', phase: 'fix_merge' };
      }
      if (context.regression) {
        return { role: 'builder', phase: 'fix_regression' };
      }
      if (context.verifier_failed) {
        return { role: 'builder', phase: 'fix_qa' };
      }
      return { role: 'verifier', phase: 'verify_issue' };

    case 'verified':
      return { role: 'verifier', phase: 'verify_pre_merge' };

    case 'closed':
      return null;

    default:
      return null;
  }
}