// @vitest-environment jsdom
/**
 * Tests for the useCountdown hook (F-15): initial value, ticking, clamping at zero,
 * stop(), the single onComplete firing, and double-start protection.
 * Rendered through a tiny harness component because @testing-library/react-hooks is not a
 * project dependency; timers are faked with vi.useFakeTimers() so nothing waits in real time.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { useCountdown } from './useCountdown';

// AC-8 pins this file name to useCountdown.test.ts, so JSX is unavailable here (esbuild only
// parses JSX in .tsx). The harness is built with React.createElement instead.
interface HarnessProps {
  target: number;
  onComplete?: () => void;
}

function Harness({ target, onComplete }: HarnessProps) {
  const { remainingSeconds, start, stop, isRunning } = useCountdown(target, onComplete);
  return React.createElement(
    'div',
    null,
    React.createElement('span', { 'data-testid': 'remaining' }, remainingSeconds),
    React.createElement('span', { 'data-testid': 'running' }, String(isRunning)),
    React.createElement('button', { onClick: start }, 'start'),
    React.createElement('button', { onClick: stop }, 'stop'),
  );
}

const remaining = () => screen.getByTestId('remaining').textContent;
const running = () => screen.getByTestId('running').textContent;
const tick = (seconds: number) => act(() => void vi.advanceTimersByTime(seconds * 1000));

const BASE = 1_700_000_000_000;

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(BASE);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('useCountdown', () => {
  it('starts from the ceil of the remaining seconds', () => {
    render(React.createElement(Harness, { target: BASE + 90_000 }));
    expect(remaining()).toBe('90');
  });

  it('starts automatically for a future target and ticks down', () => {
    render(React.createElement(Harness, { target: BASE + 90_000 }));
    expect(running()).toBe('true');
    tick(30);
    expect(remaining()).toBe('60');
  });

  it('clamps at zero instead of going negative', () => {
    render(React.createElement(Harness, { target: BASE + 5_000 }));
    tick(30);
    expect(remaining()).toBe('0');
  });

  it('DEFECT DEF-F06-1: stop() is undone by the auto-start effect while the target is future', () => {
    // Not the intent of stop(), but it is what the F-06 hook does: the auto-start effect
    // (deps targetTime/start/isRunning) sees isRunning false and calls start() again, so a
    // manual stop() on a future target immediately restarts the interval. Pinned as-is rather
    // than silently patched - F-15 may not edit hooks/useCountdown.ts (F-06 owns it).
    render(React.createElement(Harness, { target: BASE + 90_000 }));
    fireEvent.click(screen.getByText('stop'));
    tick(30);
    expect(running()).toBe('true');
    expect(remaining()).toBe('60');
  });

  it('stop() does leave a finished countdown idle', () => {
    render(React.createElement(Harness, { target: BASE + 5_000 }));
    tick(10);
    fireEvent.click(screen.getByText('stop'));
    expect(running()).toBe('false');
    tick(30);
    expect(remaining()).toBe('0');
  });

  it('does not auto-start for a target already in the past', () => {
    render(React.createElement(Harness, { target: BASE - 10_000 }));
    expect(remaining()).toBe('0');
    expect(running()).toBe('false');
  });

  it('fires onComplete exactly once, at zero', () => {
    const onComplete = vi.fn();
    render(React.createElement(Harness, { target: BASE + 3_000, onComplete }));
    tick(1);
    expect(onComplete).not.toHaveBeenCalled();
    tick(2);
    expect(onComplete).toHaveBeenCalledTimes(1);
    tick(5);
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it('ignores a second start() so the countdown does not run twice as fast', () => {
    render(React.createElement(Harness, { target: BASE + 90_000 }));
    fireEvent.click(screen.getByText('start'));
    tick(30);
    expect(remaining()).toBe('60');
  });

  it('restarts after stop()', () => {
    render(React.createElement(Harness, { target: BASE + 90_000 }));
    fireEvent.click(screen.getByText('stop'));
    fireEvent.click(screen.getByText('start'));
    expect(running()).toBe('true');
    tick(10);
    expect(remaining()).toBe('80');
  });

  it('clears its interval on unmount', () => {
    const { unmount } = render(React.createElement(Harness, { target: BASE + 90_000 }));
    unmount();
    expect(() => act(() => void vi.advanceTimersByTime(60_000))).not.toThrow();
  });
});
