// extensions/gate_checker.ts
// Gate checker: validate business logic after subagent completes

import * as fs from 'fs';
import type { Handoff, IssueState } from './state_machine.js';
import { validateHandoffSchema } from './schema_validator.js';

export interface GateResult {
  passed: boolean;
  gate: string;
  errors: string[];
}

// ============================================================
// Gate 1: after Definer: groom (defined -> groomed)
// ============================================================

export function gate1(handoff: Handoff): GateResult {
  const errors: string[] = [];

  const issuePath = `docs/issues/${handoff.issue_id}.md`;
  if (!fs.existsSync(issuePath)) {
    errors.push(`Issue file not found: ${issuePath}`);
  } else {
    const content = fs.readFileSync(issuePath, 'utf-8');
    const requiredSections = [
      '## Context',
      '## Acceptance criteria',
      '## Verification commands',
      '## Out of scope',
      '## Definition of Done',
    ];
    for (const section of requiredSections) {
      if (!content.includes(section)) {
        errors.push(`Missing section: ${section}`);
      }
    }
  }

  if (handoff.artifacts.platform_issue === null) {
    errors.push('platform_issue is null');
  }

  const evidence = handoff.evidence as Record<string, unknown>;
  if (!evidence.ac_hash) {
    errors.push('Missing ac_hash in evidence');
  }
  if (!evidence.verification_commands) {
    errors.push('Missing verification_commands in evidence');
  }

  return {
    passed: errors.length === 0,
    gate: 'gate1_groom_complete',
    errors,
  };
}

// ============================================================
// Gate 2: after Builder: implement (groomed -> built)
// ============================================================

export function gate2(handoff: Handoff): GateResult {
  const errors: string[] = [];

  const evidence = handoff.evidence as Record<string, unknown>;

  if (!evidence.branch) {
    errors.push('Missing branch in evidence');
  }
  if (!evidence.branch_sha) {
    errors.push('Missing branch_sha in evidence');
  }
  if (evidence.test_summary) {
    const ts = evidence.test_summary as Record<string, number>;
    if ((ts.failed ?? 0) > 0) {
      errors.push(`Test failures: ${ts.failed}`);
    }
  } else {
    errors.push('Missing test_summary in evidence');
  }
  if (evidence.lint_status === 'ERRORS') {
    errors.push('Lint errors detected');
  }

  return {
    passed: errors.length === 0,
    gate: 'gate2_implement_complete',
    errors,
  };
}

// ============================================================
// Gate 3: after Verifier: verify_issue (built -> verified)
// ============================================================

export function gate3(handoff: Handoff): GateResult {
  const errors: string[] = [];

  const evidence = handoff.evidence as Record<string, unknown>;

  if (!evidence.ac_results) {
    errors.push('Missing ac_results in evidence');
  } else {
    const acResults = evidence.ac_results as Record<
      string,
      { verdict: string }
    >;
    for (const [acId, result] of Object.entries(acResults)) {
      if (result.verdict !== 'PASS' && result.verdict !== 'SKIP') {
        errors.push(`${acId}: verdict is ${result.verdict}`);
      }
    }
  }

  if (!evidence.verification_commands_source) {
    errors.push('Missing verification_commands_source in evidence');
  }

  return {
    passed: errors.length === 0,
    gate: 'gate3_verify_issue_complete',
    errors,
  };
}

// ============================================================
// Gate 4: after Verifier: verify_post_merge
// ============================================================

export function gate4(handoff: Handoff): GateResult {
  const errors: string[] = [];

  const evidence = handoff.evidence as Record<string, unknown>;

  if (evidence.smoke_tests) {
    const st = evidence.smoke_tests as Record<string, number>;
    if ((st.failed ?? 0) > 0) {
      errors.push(`Smoke test failures: ${st.failed}`);
    }
  } else {
    errors.push('Missing smoke_tests in evidence');
  }

  if (evidence.regressions_detected) {
    const rd = evidence.regressions_detected as unknown[];
    if (rd.length > 0) {
      errors.push(`Regressions detected: ${rd.length}`);
    }
  }

  if (!evidence.merge_sha) {
    errors.push('Missing merge_sha in evidence');
  }

  return {
    passed: errors.length === 0,
    gate: 'gate4_post_merge_complete',
    errors,
  };
}

// ============================================================
// Unified entry point
// ============================================================

export function runGate(
  handoff: Handoff,
  _currentState: IssueState | null
): GateResult {
  const schemaResult = validateHandoffSchema(
    handoff.role,
    handoff.phase,
    handoff.artifacts.output_path
  );
  if (!schemaResult.valid) {
    return {
      passed: false,
      gate: 'schema_validation',
      errors: schemaResult.errors.map((e) => `${e.path}: ${e.message}`),
    };
  }

  if (handoff.role === 'definer' && handoff.phase === 'groom') {
    return gate1(handoff);
  }
  if (handoff.role === 'builder' && handoff.phase === 'implement') {
    return gate2(handoff);
  }
  if (handoff.role === 'verifier' && handoff.phase === 'verify_issue') {
    return gate3(handoff);
  }
  if (handoff.role === 'verifier' && handoff.phase === 'verify_post_merge') {
    return gate4(handoff);
  }

  return {
    passed: true,
    gate: 'no_gate_required',
    errors: [],
  };
}