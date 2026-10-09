// launcher/checkpoint_adapter.ts
// Launcher checkpoint integration.

import * as fs from 'fs';

export interface Checkpoint {
  schema_version: string;
  timestamp: string;
  last_seq: number;
  completed: boolean;
  orchestrator_pid: number | null;
}

const CHECKPOINT_PATH = 'docs/state/launcher_checkpoint.json';

/**
 * Error thrown when another Orchestrator instance is still running.
 */
export class DoubleInstanceError extends Error {
  constructor(pid: number) {
    super(`Orchestrator PID ${pid} is still alive. Double-instance guard.`);
    this.name = 'DoubleInstanceError';
  }
}

/**
 * Read the launcher checkpoint.
 * Returns null if the file does not exist or cannot be parsed.
 * Throws DoubleInstanceError if another Orchestrator is running.
 */
export async function readCheckpoint(): Promise<Checkpoint | null> {
  if (!fs.existsSync(CHECKPOINT_PATH)) {
    return null;
  }

  let checkpoint: Checkpoint;
  try {
    const content = fs.readFileSync(CHECKPOINT_PATH, 'utf-8');
    checkpoint = JSON.parse(content) as Checkpoint;
  } catch (err) {
    console.error('Failed to read checkpoint', err);
    return null;
  }

  if (checkpoint.schema_version !== '1.0') {
    console.warn(`Unknown checkpoint schema: ${checkpoint.schema_version}`);
    return null;
  }

  // Double-instance guard
  if (checkpoint.orchestrator_pid !== null) {
    if (isProcessAlive(checkpoint.orchestrator_pid)) {
      throw new DoubleInstanceError(checkpoint.orchestrator_pid);
    }
    // PID is dead, clear it
    checkpoint.orchestrator_pid = null;
    writeCheckpoint(checkpoint);
  }

  return checkpoint;
}

/**
 * Update the orchestrator PID in the checkpoint.
 * Pass null to clear the PID.
 */
export async function updateOrchestratorPid(
  pid: number | null
): Promise<void> {
  const checkpoint = readCheckpointOrDefault();
  checkpoint.orchestrator_pid = pid;
  checkpoint.timestamp = new Date().toISOString();
  writeCheckpoint(checkpoint);
}

/**
 * Mark the project as completed.
 */
export async function markCompleted(): Promise<void> {
  const checkpoint = readCheckpointOrDefault();
  checkpoint.completed = true;
  checkpoint.orchestrator_pid = null;
  checkpoint.timestamp = new Date().toISOString();
  writeCheckpoint(checkpoint);
}

/**
 * Save a checkpoint with the given values.
 * Used by other modules to persist state.
 */
export async function saveCheckpoint(
  lastSeq: number,
  completed: boolean
): Promise<void> {
  const checkpoint: Checkpoint = {
    schema_version: '1.0',
    timestamp: new Date().toISOString(),
    last_seq: lastSeq,
    completed,
    orchestrator_pid: null,
  };
  writeCheckpoint(checkpoint);
}

function readCheckpointOrDefault(): Checkpoint {
  if (!fs.existsSync(CHECKPOINT_PATH)) {
    return {
      schema_version: '1.0',
      timestamp: new Date().toISOString(),
      last_seq: 0,
      completed: false,
      orchestrator_pid: null,
    };
  }
  try {
    const content = fs.readFileSync(CHECKPOINT_PATH, 'utf-8');
    return JSON.parse(content) as Checkpoint;
  } catch {
    return {
      schema_version: '1.0',
      timestamp: new Date().toISOString(),
      last_seq: 0,
      completed: false,
      orchestrator_pid: null,
    };
  }
}

function writeCheckpoint(checkpoint: Checkpoint): void {
  const tmpPath = `${CHECKPOINT_PATH}.tmp`;
  fs.writeFileSync(tmpPath, JSON.stringify(checkpoint, null, 2));
  fs.renameSync(tmpPath, CHECKPOINT_PATH);
}

function isProcessAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}