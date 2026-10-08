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
  vi.restoreAllMocks();
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

  it('DEFECT DEF-F06-1 (re-pinned T17): stop() is undone by the auto-start effect while the target is future', () => {
    // T17 replaced the per-instance interval with ONE shared 1 Hz ticker, but the
    // auto-start effect (deps targetTime/start/isRunning) is unchanged: it sees
    // isRunning false and calls start() again, so a manual stop() on a future target
    // immediately re-subscribes to the shared ticker. The pinned semantics still hold
    // under the new mechanism - kept, not silently patched.
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
    expect(vi.getTimerCount()).toBe(1); // the one shared ticker
    unmount();
    expect(vi.getTimerCount()).toBe(0); // no interval left behind
    expect(() => act(() => void vi.advanceTimersByTime(60_000))).not.toThrow(); // no post-unmount updates
  });

  it('T17 AC-4: drives N>=3 concurrent countdowns from exactly one shared 1 Hz interval', () => {
    const intervalSpy = vi.spyOn(globalThis, 'setInterval');
    const a = render(React.createElement(Harness, { target: BASE + 90_000 }));
    const b = render(React.createElement(Harness, { target: BASE + 45_000 }));
    const c = render(React.createElement(Harness, { target: BASE + 10_000 }));
    // Three consumers, ONE interval, at 1000 ms.
    expect(intervalSpy).toHaveBeenCalledTimes(1);
    expect(intervalSpy.mock.calls[0][1]).toBe(1000);
    tick(10);
    // Each display decrements independently.
    expect(a.container.querySelector('[data-testid="remaining"]')?.textContent).toBe('80');
    expect(b.container.querySelector('[data-testid="remaining"]')?.textContent).toBe('35');
    expect(c.container.querySelector('[data-testid="remaining"]')?.textContent).toBe('0');
    // Unmounting consumers leaves the shared ticker alive for the rest, and the
    // interval is never re-created.
    a.unmount();
    expect(vi.getTimerCount()).toBe(1);
    b.unmount();
    c.unmount();
    expect(vi.getTimerCount()).toBe(0);
    expect(intervalSpy).toHaveBeenCalledTimes(1);
  });

  it('T17 AC-4: each countdown fires its own onComplete exactly once at zero on the shared ticker', () => {
    const onCompleteA = vi.fn();
    const onCompleteB = vi.fn();
    render(React.createElement(Harness, { target: BASE + 90_000, onComplete: onCompleteA }));
    const b = render(React.createElement(Harness, { target: BASE + 10_000, onComplete: onCompleteB }));
    tick(10); // b reaches zero first; a keeps ticking
    expect(onCompleteB).toHaveBeenCalledTimes(1);
    expect(onCompleteA).not.toHaveBeenCalled();
    tick(80); // a reaches zero on the same shared ticker
    expect(onCompleteA).toHaveBeenCalledTimes(1);
    expect(onCompleteB).toHaveBeenCalledTimes(1);
    b.unmount();
  });
});
