/**
 * Countdown hook for timed displays.
 * AC-11: exports remainingSeconds, start, stop
 * 
 * @param targetTime - The target end time (Date or number in ms)
 * @param onComplete - Callback when countdown reaches zero
 * @returns Object with remainingSeconds, start, stop, isRunning
 */
import { useEffect, useState, useCallback, useRef } from 'react';

interface UseCountdownReturn {
  remainingSeconds: number;
  start: () => void;
  stop: () => void;
  isRunning: boolean;
}

export function useCountdown(
  targetTime: Date | number,
  onComplete?: () => void
): UseCountdownReturn {
  const [remainingSeconds, setRemainingSeconds] = useState<number>(() => {
    const target = targetTime instanceof Date ? targetTime.getTime() : targetTime;
    return Math.max(0, Math.ceil((target - Date.now()) / 1000));
  });
  const [isRunning, setIsRunning] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onCompleteRef = useRef(onComplete);

  // Update onComplete ref when prop changes
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsRunning(false);
  }, []);

  const start = useCallback(() => {
    if (intervalRef.current) return;

    setIsRunning(true);
    intervalRef.current = setInterval(() => {
      const target = targetTime instanceof Date ? targetTime.getTime() : targetTime;
      const remaining = Math.max(0, Math.ceil((target - Date.now()) / 1000));
      setRemainingSeconds(remaining);

      if (remaining === 0) {
        stop();
        if (onCompleteRef.current) {
          onCompleteRef.current();
        }
      }
    }, 1000);
  }, [targetTime, stop]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  // Start automatically on mount if targetTime is in the future
  useEffect(() => {
    const target = targetTime instanceof Date ? targetTime.getTime() : targetTime;
    if (target > Date.now() && !isRunning) {
      start();
    }
  }, [targetTime, start, isRunning]);

  return { remainingSeconds, start, stop, isRunning };
}

export default useCountdown;
