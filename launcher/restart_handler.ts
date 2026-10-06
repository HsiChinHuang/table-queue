// launcher/restart_handler.ts
// Restart policy

export enum ExitReason {
  COMPLETED = 'COMPLETED',
  SCHEDULED_RESTART = 'SCHEDULED_RESTART',
  CRASHED = 'CRASHED',
  USER_STOPPED = 'USER_STOPPED',
}

export interface RestartPolicy {
  maxAttempts: number;
  backoffSeconds: number[];
  resetOnScheduledRestart: boolean;
}

export const DEFAULT_POLICY: RestartPolicy = {
  maxAttempts: 10,
  backoffSeconds: [5, 15, 45, 120, 300],
  resetOnScheduledRestart: true,
};

export function shouldRestart(
  reason: ExitReason,
  attempts: number,
  policy: RestartPolicy = DEFAULT_POLICY
): boolean {
  if (reason === ExitReason.COMPLETED) return false;
  if (reason === ExitReason.USER_STOPPED) return false;
  if (reason === ExitReason.SCHEDULED_RESTART) return true;
  if (reason === ExitReason.CRASHED) {
    if (policy.maxAttempts === 0) return true;
    return attempts < policy.maxAttempts;
  }
  return false;
}

export function getBackoffSeconds(
  attempts: number,
  policy: RestartPolicy = DEFAULT_POLICY
): number {
  const index = Math.min(attempts - 1, policy.backoffSeconds.length - 1);
  const safeIndex = Math.max(0, index);
  const value = policy.backoffSeconds[safeIndex];
  // Fallback to 300s if backoffSeconds is empty or index is out of range
  return value ?? 300;
}

/**
 * Whether the restart counter should be reset after a scheduled restart.
 */
export function shouldResetCounter(
  reason: ExitReason,
  policy: RestartPolicy = DEFAULT_POLICY
): boolean {
  if (reason === ExitReason.SCHEDULED_RESTART) {
    return policy.resetOnScheduledRestart;
  }
  return false;
}