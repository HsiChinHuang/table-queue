/**
 * Countdown hook for timed displays.
 * AC-11: exports remainingSeconds, start, stop
 * T17 AC-4: every countdown in the app is driven by ONE shared 1 Hz ticker
 * (module-level, with a subscriber set) instead of a per-instance interval.
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

// T17 AC-4: the ONE app-wide 1 Hz countdown ticker. It exists only while at
// least one subscriber is alive - the first subscriber starts it, the last
// subscriber removes it - so an unmounted tree leaves no interval behind.
type TickListener = () => void;
let tickerListeners: Set<TickListener> | null = null;
let tickerTimer: ReturnType<typeof setInterval> | null = null;

/** Subscribe to the shared 1 Hz ticker; returns the unsubscribe function. */
export function subscribeCountdownTicker(listener: TickListener): () => void {
  if (!tickerListeners) tickerListeners = new Set();
  if (tickerListeners.size === 0) {
    tickerTimer = setInterval(() => {
      if (tickerListeners) tickerListeners.forEach((l) => l());
    }, 1000);
  }
  tickerListeners.add(listener);
  return () => {
    if (!tickerListeners) return;
    tickerListeners.delete(listener);
    if (tickerListeners.size === 0) {
      tickerListeners = null;
      if (tickerTimer) {
        clearInterval(tickerTimer);
        tickerTimer = null;
      }
    }
  };
}

export function useCountdown(
  targetTime: Date | number,
  onComplete?: () => void
): UseCountdownReturn {
  const target = targetTime instanceof Date ? targetTime.getTime() : targetTime;

  const [remainingSeconds, setRemainingSeconds] = useState<number>(() =>
    Math.max(0, Math.ceil((target - Date.now()) / 1000)),
  );
  const [isRunning, setIsRunning] = useState(false);

  const onCompleteRef = useRef(onComplete);
  const targetRef = useRef(target);
  const runningRef = useRef(false);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  // Update onComplete ref when prop changes
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  // Keep the subscription pointing at the freshest target (the old per-instance
  // interval closed over a stale targetTime; the shared ticker reads targetRef).
  useEffect(() => {
    targetRef.current = target;
    setRemainingSeconds(Math.max(0, Math.ceil((target - Date.now()) / 1000)));
  }, [target]);

  const stop = useCallback(() => {
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }
    runningRef.current = false;
    setIsRunning(false);
  }, []);

  const start = useCallback(() => {
    if (runningRef.current) return; // second start() must not double the tick rate

    runningRef.current = true;
    setIsRunning(true);
    unsubscribeRef.current = subscribeCountdownTicker(() => {
      const remaining = Math.max(0, Math.ceil((targetRef.current - Date.now()) / 1000));
      setRemainingSeconds(remaining);

      if (remaining === 0) {
        stop();
        if (onCompleteRef.current) {
          onCompleteRef.current();
        }
      }
    });
  }, [stop]);

  // Unmount: drop this subscription (the shared ticker dies with the last one).
  useEffect(() => {
    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
      runningRef.current = false;
    };
  }, []);

  // Start automatically on mount if targetTime is in the future
  useEffect(() => {
    if (target > Date.now() && !isRunning) {
      start();
    }
  }, [target, start, isRunning]);

  return { remainingSeconds, start, stop, isRunning };
}

export default useCountdown;
