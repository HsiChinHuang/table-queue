// launcher/index.ts
// External Launcher: starts, monitors, and restarts the Orchestrator

import * as fs from 'fs';
import * as path from 'path';
import { loadConfig } from './config_loader.js';
import {
  readCheckpoint,
  updateOrchestratorPid,
  markCompleted,
} from './checkpoint_adapter.js';
import { ExitReason, getBackoffSeconds } from './restart_handler.js';
import { logger } from './logger.js';
import { spawn, type ChildProcess } from 'child_process';

const DEFAULT_MAX_ATTEMPTS = 10;
const COMPLETE_PATH = 'docs/state/COMPLETE.md';

// Module-level reference so signal handlers can access the current child
let currentOrchestrator: ChildProcess | null = null;

/**
 * Resolve the platform-appropriate GIT_ASKPASS helper path.
 * Git for Windows requires a .cmd file; Unix-like systems use .sh.
 */
function resolveGitAskpassPath(): string {
  const script = process.platform === 'win32'
    ? 'scripts/git_askpass.cmd'
    : 'scripts/git_askpass.sh';
  return path.resolve(script);
}

async function main(): Promise<void> {
  logger.info('Launcher started');

  const config = await loadConfig();

  const autoRestart = config.effective['launcher.auto_restart'] !== false;
  const maxAttempts =
    (config.effective['launcher.max_restart_attempts'] as number) ??
    DEFAULT_MAX_ATTEMPTS;

  if (!autoRestart) {
    logger.info('Auto-restart is DISABLED. Launcher will exit on crash.');
  }
  if (maxAttempts === 0) {
    logger.warn('max_restart_attempts = 0 (unlimited). Risk of infinite loop.');
  }

  const askpassPath = resolveGitAskpassPath();
  if (!fs.existsSync(askpassPath)) {
    logger.warn(
      `GIT_ASKPASS helper not found at ${askpassPath}. ` +
        'git push will fall back to interactive credentials.'
    );
  } else {
    logger.info(`GIT_ASKPASS helper: ${askpassPath}`);
  }

  let restartAttempts = 0;

  for (;;) {
    // Check launcher checkpoint
    let checkpoint;
    try {
      checkpoint = await readCheckpoint();
    } catch (err) {
      // Double-instance guard triggered
      logger.error((err as Error).message);
      process.exit(1);
    }

    // If checkpoint says completed, exit before spawning
    if (checkpoint && checkpoint.completed) {
      if (fs.existsSync(COMPLETE_PATH)) {
        logger.info('Project already completed. Launcher exiting.');
        process.exit(0);
      }
      // Inconsistent state: checkpoint says completed but COMPLETE.md missing
      logger.warn(
        'Checkpoint says completed=true but COMPLETE.md is missing. ' +
          'Resetting checkpoint to completed=false.'
      );
      await resetCheckpointCompleted();
    }

    logger.info(
      checkpoint
        ? `Checkpoint found: completed=${checkpoint.completed}, last_seq=${checkpoint.last_seq}`
        : 'No checkpoint found, starting fresh'
    );

    // Start Orchestrator
    const exitReason = await runOrchestrator(config, askpassPath);

    // Normal completion -> check COMPLETE.md before trusting exit code 0
    if (exitReason === ExitReason.COMPLETED) {
      if (fs.existsSync(COMPLETE_PATH)) {
        logger.info('Orchestrator completed normally. Launcher exiting.');
        await markCompleted();
        process.exit(0);
      }
      // Exit code 0 but no COMPLETE.md — treat as crash
      logger.warn(
        'Orchestrator exited with code 0 but COMPLETE.md is missing. ' +
          'Treating as crash.'
      );
      // Fall through to crash handling
    }

    // User stopped -> exit
    if (exitReason === ExitReason.USER_STOPPED) {
      logger.info('User stopped. Launcher exiting.');
      process.exit(0);
    }

    // Auto-restart disabled -> exit
    if (!autoRestart) {
      logger.warn('Auto-restart is disabled. Exiting due to crash.');
      process.exit(1);
    }

    // Crashed (or COMPLETED without COMPLETE.md) -> check retry count
    if (exitReason === ExitReason.CRASHED || exitReason === ExitReason.COMPLETED) {
      restartAttempts++;
      if (maxAttempts > 0 && restartAttempts >= maxAttempts) {
        logger.error(`Max restart attempts (${maxAttempts}) reached. Exiting.`);
        process.exit(1);
      }
      const backoff = getBackoffSeconds(restartAttempts);
      logger.warn(
        `Orchestrator crashed. Restarting in ${backoff}s ` +
          `(attempt ${restartAttempts}/${maxAttempts || 'inf'})`
      );
      await sleep(backoff * 1000);
    }

    // Scheduled restart -> reset counter
    if (exitReason === ExitReason.SCHEDULED_RESTART) {
      logger.info('Scheduled restart. Restarting immediately.');
      restartAttempts = 0;
    }
  }
}

/**
 * Run Orchestrator once and resolve with the exit reason.
 * Updates the checkpoint PID while running.
 * Injects GIT_ASKPASS so git push uses the API_TOKEN from .env.
 */
async function runOrchestrator(
  config: {
    env: Record<string, string>;
    effective: Record<string, unknown>;
  },
  askpassPath: string
): Promise<ExitReason> {
  return new Promise((resolve) => {
    const orchestrator = spawn(
      'pi',
      [
        'run',
        '--skill', 'skills/orchestrator/SKILL.md',
      ],
      {
        env: {
          ...process.env,
          ...config.env,
          GIT_ASKPASS: askpassPath,
          GIT_TERMINAL_PROMPT: '0',
        },
        stdio: 'inherit',
        shell: true,
      }
    );

    currentOrchestrator = orchestrator;

    // Record the PID so double-instance guard can detect it
    if (orchestrator.pid) {
      updateOrchestratorPid(orchestrator.pid);
    } else {
      logger.warn('Orchestrator spawned without a PID');
    }

    orchestrator.on('error', (err) => {
      logger.error(`Failed to spawn Orchestrator: ${err.message}`);
      currentOrchestrator = null;
      updateOrchestratorPid(null);
      resolve(ExitReason.CRASHED);
    });

    orchestrator.on('exit', (code, signal) => {
      currentOrchestrator = null;

      // Clear PID from checkpoint
      updateOrchestratorPid(null);

      if (signal === 'SIGTERM' || signal === 'SIGINT') {
        resolve(ExitReason.USER_STOPPED);
      } else if (code === 0) {
        resolve(ExitReason.COMPLETED);
      } else if (code === 42) {
        resolve(ExitReason.SCHEDULED_RESTART);
      } else {
        resolve(ExitReason.CRASHED);
      }
    });
  });
}

/**
 * Reset checkpoint's completed flag to false.
 * Used when checkpoint says completed=true but COMPLETE.md is missing.
 */
async function resetCheckpointCompleted(): Promise<void> {
  const checkpointPath = 'docs/state/launcher_checkpoint.json';
  try {
    const content = fs.readFileSync(checkpointPath, 'utf-8');
    const checkpoint = JSON.parse(content);
    checkpoint.completed = false;
    checkpoint.timestamp = new Date().toISOString();
    const tmp = `${checkpointPath}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(checkpoint, null, 2));
    fs.renameSync(tmp, checkpointPath);
  } catch (err) {
    logger.error(`Failed to reset checkpoint: ${(err as Error).message}`);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Register signal handlers once
process.on('SIGTERM', () => {
  logger.info('SIGTERM received. Forwarding to Orchestrator.');
  if (currentOrchestrator) {
    currentOrchestrator.kill('SIGTERM');
  } else {
    process.exit(0);
  }
});

process.on('SIGINT', () => {
  logger.info('SIGINT received. Forwarding to Orchestrator.');
  if (currentOrchestrator) {
    currentOrchestrator.kill('SIGINT');
  } else {
    process.exit(0);
  }
});

main().catch((err) => {
  logger.error('Launcher fatal error', err);
  process.exit(1);
});