// extensions/slot_manager.ts
// Slot assignment and priority computation

import type { IssueState, Role, Phase } from './state_machine.js';

// ============================================================
// Type definitions
// ============================================================

export interface Issue {
  id: string;
  title: string;
  state: IssueState;
  depends: string[];
  created_at: string;
  size: 'S' | 'M' | 'L';
  is_critical_path: boolean;
  direct_blocked: number;
  transitive_blocked: number;
  waiting_since: string | null;
  labels: string[];
}

export interface SlotAssignment {
  issue_id: string;
  role: Role;
  phase: Phase;
  priority: number;
}

export interface SlotConfig {
  max_slots: number;
  pause_threshold: number;
  pause_threshold_min: number;
  pause_threshold_max: number;
  starvation_warn_hours: number;
  starvation_blocker_hours: number;
}

// ============================================================
// Priority computation
// ============================================================

export function computePriority(issue: Issue): number {
  let priority = 0;

  // Base score
  priority += issue.direct_blocked * 2;
  priority += issue.transitive_blocked * 1;

  // Critical path bonus
  if (issue.is_critical_path) {
    priority += 1;
  }

  // Starvation bonus
  if (issue.waiting_since) {
    const waitHours =
      (Date.now() - new Date(issue.waiting_since).getTime()) / 3600000;
    if (waitHours > 24) {
      priority += Math.floor(waitHours / 24);
    }
  }

  return priority;
}

// ============================================================
// Sorting
// ============================================================

export function sortReadyIssues(issues: Issue[]): Issue[] {
  return [...issues].sort((a, b) => {
    // 1. Priority descending
    const pa = computePriority(a);
    const pb = computePriority(b);
    if (pa !== pb) return pb - pa;

    // 2. Older creation time first
    const ta = new Date(a.created_at).getTime();
    const tb = new Date(b.created_at).getTime();
    if (ta !== tb) return ta - tb;

    // 3. Smaller size first
    const sizeOrder = { S: 0, M: 1, L: 2 };
    if (sizeOrder[a.size] !== sizeOrder[b.size]) {
      return sizeOrder[a.size] - sizeOrder[b.size];
    }

    // 4. Smaller local ID
    return a.id.localeCompare(b.id);
  });
}

// ============================================================
// Slot assignment
// ============================================================

export function assignSlots(
  readyIssues: Issue[],
  activeSlots: number,
  config: SlotConfig,
  mergeQueueLength: number
): SlotAssignment[] {
  const assignments: SlotAssignment[] = [];
  const available = config.max_slots - activeSlots;

  if (available <= 0) {
    return assignments;
  }

  // Check whether Builder spawn should be paused
  const shouldPauseBuilder = mergeQueueLength >= config.pause_threshold;

  // Sort
  const sorted = sortReadyIssues(readyIssues);

  let assigned = 0;
  for (const issue of sorted) {
    if (assigned >= available) break;

    const roleAndPhase = determineRoleAndPhase(issue);

    // If Builder is paused, skip Builder-related issues
    if (shouldPauseBuilder && roleAndPhase.role === 'builder') {
      continue;
    }

    assignments.push({
      issue_id: issue.id,
      role: roleAndPhase.role,
      phase: roleAndPhase.phase,
      priority: computePriority(issue),
    });
    assigned++;
  }

  return assignments;
}

// ============================================================
// Role and phase determination
// ============================================================

export function determineRoleAndPhase(issue: Issue): {
  role: Role;
  phase: Phase;
} {
  const hasLabel = (label: string): boolean => issue.labels.includes(label);

  switch (issue.state) {
    case 'defined':
      // If groomed (has groomed label), proceed to Builder
      if (hasLabel('groomed')) {
        return { role: 'builder', phase: 'implement' };
      }
      return { role: 'definer', phase: 'groom' };

    case 'groomed':
      return { role: 'builder', phase: 'implement' };

    case 'built':
      if (hasLabel('merge_conflict')) {
        return { role: 'builder', phase: 'fix_merge' };
      }
      if (hasLabel('regression')) {
        return { role: 'builder', phase: 'fix_regression' };
      }
      if (hasLabel('verifier_failed')) {
        return { role: 'builder', phase: 'fix_qa' };
      }
      return { role: 'verifier', phase: 'verify_issue' };

    case 'verified':
      return { role: 'verifier', phase: 'verify_pre_merge' };

    case 'closed':
      throw new Error(`Cannot assign slot for closed issue ${issue.id}`);

    default:
      throw new Error(`Unknown state: ${issue.state}`);
  }
}

// ============================================================
// Dynamic pause threshold
// ============================================================

export function adjustPauseThreshold(
  current: number,
  mergeQueueHistory: number[],
  config: SlotConfig
): number {
  if (mergeQueueHistory.length < 5) return current;

  const recent = mergeQueueHistory.slice(-3);
  const allGrowing = recent.every(
    (v, i) => i === 0 || v > (recent[i - 1] ?? 0)
  );
  const allEmpty = mergeQueueHistory.slice(-5).every((v) => v === 0);

  if (allGrowing) {
    return Math.max(config.pause_threshold_min, current - 1);
  }
  if (allEmpty) {
    return Math.min(config.pause_threshold_max, current + 1);
  }
  return current;
}

// ============================================================
// Starvation detection
// ============================================================

export interface StarvationReport {
  issue_id: string;
  wait_hours: number;
  severity: 'warn' | 'blocker';
}

export function detectStarvation(
  issues: Issue[],
  config: SlotConfig
): StarvationReport[] {
  const reports: StarvationReport[] = [];
  const now = Date.now();

  for (const issue of issues) {
    if (!issue.waiting_since) continue;
    const waitHours =
      (now - new Date(issue.waiting_since).getTime()) / 3600000;

    if (waitHours > config.starvation_blocker_hours) {
      reports.push({
        issue_id: issue.id,
        wait_hours: waitHours,
        severity: 'blocker',
      });
    } else if (waitHours > config.starvation_warn_hours) {
      reports.push({
        issue_id: issue.id,
        wait_hours: waitHours,
        severity: 'warn',
      });
    }
  }

  return reports;
}

// ============================================================
// Slot liveness check
// ============================================================

export interface SlotLivenessCheck {
  slot_id: string;
  issue_id: string;
  is_stale: boolean;
  should_force_release: boolean;
}

/**
 * Compute slot liveness from last_activity_at timestamps.
 *
 * The timestamps are synced from pi-subagents status.json by the
 * Orchestrator on each liveness check; this function is a pure
 * computation over the provided snapshot values.
 */
export function checkSlotLiveness(
  slots: Array<{
    slot_id: string;
    issue_id: string;
    last_activity_at: string;
  }>,
  staleMinutes: number,
  forceReleaseMultiplier: number
): SlotLivenessCheck[] {
  const now = Date.now();
  const staleMs = staleMinutes * 60 * 1000;
  const forceMs = staleMs * forceReleaseMultiplier;

  return slots.map((slot) => {
    const last = new Date(slot.last_activity_at).getTime();
    const elapsed = now - last;

    return {
      slot_id: slot.slot_id,
      issue_id: slot.issue_id,
      is_stale: elapsed > staleMs,
      should_force_release: elapsed > forceMs,
    };
  });
}