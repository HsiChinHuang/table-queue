// extensions/recovery.ts
// Recovery logic: rebuild state when Orchestrator boots

import * as fs from 'fs';
import { execSync } from 'child_process';
import { validateStateFile } from './schema_validator.js';

// ============================================================
// Paths
// ============================================================

const PATH_SNAPSHOT = 'docs/state/snapshot.json';
const PATH_SEQ = 'docs/state/seq.txt';
const PATH_MERGE_CP = 'docs/state/merge_cp.json';
const PATH_IDEMPOTENCY = 'docs/state/idempotency.json';
const PATH_LAUNCHER_CP = 'docs/state/launcher_checkpoint.json';
const PATH_CONFIG_SNAPSHOT = 'docs/state/config_snapshot.json';

// ============================================================
// Type definitions
// ============================================================

export interface Snapshot {
  schema_version: string;
  updated_at: string;
  last_seq: number;
  slots: Slot[];
  merge_queue: MergeQueueEntry[];
  active_issues: string[];
}

export interface Slot {
  slot_id: string;
  issue_id: string;
  role: string;
  phase: string;
  spawn_at: string;
  last_heartbeat: string;
  worktree_path: string | null;
}

export interface MergeQueueEntry {
  issue_id: string;
  verifier_pass_at: string;
  priority: number;
  depends_merged: boolean;
}

export interface MergeCheckpoint {
  schema_version: string;
  issue_id: string;
  step: number;
  state: string;
  timestamp: string;
  pre_merge_sha: string | null;
  merge_sha: string | null;
  test_result: {
    total: number;
    passed: number;
    failed: number;
  } | null;
}

export interface HeartbeatConfig {
  stale_minutes: number;
  force_release_multiplier: number;
}

export const DEFAULT_HEARTBEAT: HeartbeatConfig = {
  stale_minutes: 10,
  force_release_multiplier: 2,
};

// ============================================================
// Recovery result
// ============================================================

export interface RecoveryResult {
  success: boolean;
  start_mode: 'FRESH' | 'RESUME';
  actions: RecoveryAction[];
  errors: string[];
}

export interface RecoveryAction {
  type: string;
  target: string;
  reason: string;
}

// ============================================================
// Heartbeat config loading
// ============================================================

/**
 * Load heartbeat configuration from config_snapshot.json.
 *
 * Falls back to DEFAULT_HEARTBEAT if:
 * - File does not exist
 * - File is not valid JSON
 * - `values` is missing or invalid
 * - `heartbeat.stale_minutes` or `heartbeat.force_release_multiplier` is missing or wrong type
 */
export function loadHeartbeatConfig(): HeartbeatConfig {
  try {
    const content = fs.readFileSync(PATH_CONFIG_SNAPSHOT, 'utf-8');
    const snapshot = JSON.parse(content) as {
      values?: Record<string, unknown>;
    };
    const values = snapshot.values || {};

    const stale = values['heartbeat.stale_minutes'];
    const forceMultiplier = values['heartbeat.force_release_multiplier'];

    return {
      stale_minutes:
        typeof stale === 'number' && stale > 0
          ? stale
          : DEFAULT_HEARTBEAT.stale_minutes,
      force_release_multiplier:
        typeof forceMultiplier === 'number' && forceMultiplier > 0
          ? forceMultiplier
          : DEFAULT_HEARTBEAT.force_release_multiplier,
    };
  } catch {
    return { ...DEFAULT_HEARTBEAT };
  }
}

// ============================================================
// Core recovery logic
// ============================================================

/**
 * Execute the recovery flow.
 */
export async function recoverState(): Promise<RecoveryResult> {
  const actions: RecoveryAction[] = [];
  const errors: string[] = [];

  // Load heartbeat config first
  const heartbeat = loadHeartbeatConfig();

  // Step 1: Read launcher checkpoint
  const checkpoint = readLauncherCheckpoint();
  if (!checkpoint) {
    return {
      success: true,
      start_mode: 'FRESH',
      actions: [{ type: 'FRESH_START', target: '', reason: 'no checkpoint' }],
      errors: [],
    };
  }
  if (checkpoint.completed) {
    return {
      success: true,
      start_mode: 'FRESH',
      actions: [
        { type: 'FRESH_START', target: '', reason: 'project completed' },
      ],
      errors: [],
    };
  }

  // Step 2: Read snapshot
  const snapshot = readSnapshot();
  if (!snapshot) {
    return {
      success: true,
      start_mode: 'FRESH',
      actions: [
        { type: 'FRESH_START', target: '', reason: 'no snapshot' },
      ],
      errors: [],
    };
  }

  // Step 3: Validate snapshot schema
  const snapshotValidation = validateStateFile('snapshot', PATH_SNAPSHOT);
  if (!snapshotValidation.valid) {
    actions.push({
      type: 'SCHEMA_VALIDATION_FAILED',
      target: PATH_SNAPSHOT,
      reason: formatSchemaErrors(snapshotValidation.errors),
    });
    errors.push(`snapshot.json schema validation failed`);
    return {
      success: false,
      start_mode: 'RESUME',
      actions,
      errors,
    };
  }

  // Step 4: Validate merge_cp schema (if exists)
  if (fs.existsSync(PATH_MERGE_CP)) {
    const mergeCpValidation = validateStateFile('merge_cp', PATH_MERGE_CP);
    if (!mergeCpValidation.valid) {
      actions.push({
        type: 'SCHEMA_VALIDATION_FAILED',
        target: PATH_MERGE_CP,
        reason: formatSchemaErrors(mergeCpValidation.errors),
      });
      errors.push(`merge_cp.json schema validation failed`);
      return {
        success: false,
        start_mode: 'RESUME',
        actions,
        errors,
      };
    }
  }

  // Step 5: Validate idempotency schema (if exists)
  if (fs.existsSync(PATH_IDEMPOTENCY)) {
    const idemValidation = validateStateFile(
      'idempotency',
      PATH_IDEMPOTENCY
    );
    if (!idemValidation.valid) {
      actions.push({
        type: 'SCHEMA_VALIDATION_FAILED',
        target: PATH_IDEMPOTENCY,
        reason: formatSchemaErrors(idemValidation.errors),
      });
      errors.push(`idempotency.json schema validation failed`);
      return {
        success: false,
        start_mode: 'RESUME',
        actions,
        errors,
      };
    }
  }

  // Step 6: Verify seq consistency
  const seq = readSeq();
  if (seq !== snapshot.last_seq) {
    actions.push({
      type: 'SEQ_SYNC',
      target: 'seq.txt',
      reason: `seq.txt (${seq}) != snapshot.last_seq (${snapshot.last_seq})`,
    });
    writeSeq(snapshot.last_seq);
  }

  // Step 7: Recover merge checkpoint
  const mergeCp = readMergeCheckpoint();
  if (mergeCp) {
    const mergeAction = recoverMerge(mergeCp);
    if (mergeAction) {
      actions.push(mergeAction);
    }
  }

  // Step 8: Recover slots
  const validSlots: Slot[] = [];
  const now = Date.now();
  const staleMs = heartbeat.stale_minutes * 60 * 1000;
  const forceMs = staleMs * heartbeat.force_release_multiplier;

  for (const slot of snapshot.slots) {
    // Check worktree
    if (slot.worktree_path && !fs.existsSync(slot.worktree_path)) {
      actions.push({
        type: 'SLOT_RELEASED',
        target: slot.issue_id,
        reason: 'worktree missing',
      });
      continue;
    }

    // Check heartbeat
    const lastHeartbeat = new Date(slot.last_heartbeat).getTime();
    const elapsed = now - lastHeartbeat;

    if (elapsed > forceMs) {
      actions.push({
        type: 'SLOT_FORCE_RELEASED',
        target: slot.issue_id,
        reason: `heartbeat stale beyond force threshold (${heartbeat.stale_minutes}min * ${heartbeat.force_release_multiplier})`,
      });
      continue;
    }

    if (elapsed > staleMs) {
      actions.push({
        type: 'SLOT_RELEASED',
        target: slot.issue_id,
        reason: `heartbeat stale (> ${heartbeat.stale_minutes}min)`,
      });
      continue;
    }

    validSlots.push(slot);
  }

  // Step 9: Update snapshot
  snapshot.slots = validSlots;
  snapshot.active_issues = validSlots.map((s) => s.issue_id);
  snapshot.updated_at = new Date().toISOString();
  writeSnapshot(snapshot);

  // Step 10: Record RECOVERY_OK
  actions.push({
    type: 'RECOVERY_OK',
    target: '',
    reason: `slots=${validSlots.length}, queue=${snapshot.merge_queue.length}`,
  });

  return {
    success: true,
    start_mode: 'RESUME',
    actions,
    errors,
  };
}

/**
 * Format schema errors into a short summary for logging.
 */
function formatSchemaErrors(
  errors: Array<{ path: string; message: string }>
): string {
  return errors
    .slice(0, 3)
    .map((e) => `${e.path}: ${e.message}`)
    .join('; ');
}

// ============================================================
// Merge recovery
// ============================================================

function recoverMerge(cp: MergeCheckpoint): RecoveryAction | null {
  switch (cp.state) {
    case 'fetched':
      return {
        type: 'MERGE_RESUME',
        target: cp.issue_id,
        reason: 'from step 2 (reset)',
      };

    case 'reset':
      return {
        type: 'MERGE_RESUME',
        target: cp.issue_id,
        reason: 'from step 3 (merge)',
      };

    case 'merged':
      if (localMainHasMerge(cp.merge_sha)) {
        return {
          type: 'MERGE_RESUME',
          target: cp.issue_id,
          reason: 'local has merge, from step 5 (test)',
        };
      }
      return {
        type: 'MERGE_ABORT',
        target: cp.issue_id,
        reason: 'local missing merge',
      };

    case 'tested':
      if (cp.test_result && cp.test_result.failed === 0) {
        return {
          type: 'MERGE_RESUME',
          target: cp.issue_id,
          reason: 'tests passed, from step 6 (push)',
        };
      }
      return {
        type: 'MERGE_ROLLBACK',
        target: cp.issue_id,
        reason: 'tests failed',
      };

    case 'pushed':
      if (originMainSha() === cp.merge_sha) {
        return {
          type: 'MERGE_RESUME',
          target: cp.issue_id,
          reason: 'pushed, from step 7 (closure)',
        };
      }
      return {
        type: 'MERGE_ABORT',
        target: cp.issue_id,
        reason: 'push state mismatch',
      };

    case 'closed':
      fs.unlinkSync(PATH_MERGE_CP);
      return {
        type: 'MERGE_COMPLETE',
        target: cp.issue_id,
        reason: 'already closed',
      };

    default:
      return {
        type: 'MERGE_ABORT',
        target: cp.issue_id,
        reason: `unknown state: ${cp.state}`,
      };
  }
}

// ============================================================
// File I/O
// ============================================================

function readLauncherCheckpoint(): { completed: boolean } | null {
  try {
    const content = fs.readFileSync(PATH_LAUNCHER_CP, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

function readSnapshot(): Snapshot | null {
  try {
    const content = fs.readFileSync(PATH_SNAPSHOT, 'utf-8');
    const parsed = JSON.parse(content);
    if (!parsed.slots || parsed.slots.length === 0) {
      return null;
    }
    return parsed as Snapshot;
  } catch {
    return null;
  }
}

function writeSnapshot(snapshot: Snapshot): void {
  const tmp = `${PATH_SNAPSHOT}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(snapshot, null, 2));
  fs.renameSync(tmp, PATH_SNAPSHOT);
}

function readSeq(): number {
  try {
    return parseInt(fs.readFileSync(PATH_SEQ, 'utf-8'), 10);
  } catch {
    return 0;
  }
}

function writeSeq(seq: number): void {
  fs.writeFileSync(PATH_SEQ, String(seq));
}

function readMergeCheckpoint(): MergeCheckpoint | null {
  try {
    const content = fs.readFileSync(PATH_MERGE_CP, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

// ============================================================
// Git helpers
// ============================================================

/**
 * Check whether local main contains the given merge commit.
 */
function localMainHasMerge(mergeSha: string | null): boolean {
  if (!mergeSha) return false;
  try {
    execSync(`git merge-base --is-ancestor ${mergeSha} main`, {
      stdio: 'pipe',
    });
    return true;
  } catch {
    return false;
  }
}

/**
 * Get the SHA of origin/main.
 */
function originMainSha(): string | null {
  try {
    return execSync('git rev-parse origin/main', { encoding: 'utf-8' }).trim();
  } catch {
    return null;
  }
}