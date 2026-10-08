// @vitest-environment jsdom
/**
 * Countdown (F-15): mm:ss formatting, the red zero state, className pass-through and the
 * title attribute. Timers are faked so the tick is deterministic.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
import { Countdown } from './Countdown';

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

const tick = (seconds: number) => act(() => void vi.advanceTimersByTime(seconds * 1000));

describe('Countdown', () => {
  it('formats the remaining time as mm:ss', () => {
    render(<Countdown targetTime={BASE + 75_000} />);
    expect(screen.getByText('01:15')).toBeTruthy();
  });

  it('pads single-digit minutes and seconds', () => {
    render(<Countdown targetTime={BASE + 9_000} />);
    expect(screen.getByText('00:09')).toBeTruthy();
  });

  it('turns red exactly at zero', () => {
    render(<Countdown targetTime={BASE + 3_000} />);
    const before = screen.getByText('00:03');
    expect(before.className).toContain('text-text-primary');
    tick(3);
    const zero = screen.getByText('00:00');
    expect(zero.className).toContain('text-error');
    expect(zero.className).toContain('font-bold');
  });

  it('appends the caller className', () => {
    render(<Countdown targetTime={BASE + 60_000} className="text-xl" />);
    expect(screen.getByText('01:00').className).toContain('text-xl');
  });

  it('exposes the same value through the title attribute and stays aria-live off', () => {
    const { container } = render(<Countdown targetTime={BASE + 60_000} />);
    const el = container.querySelector('span');
    expect(el?.getAttribute('title')).toBe('Time remaining: 01:00');
    expect(el?.getAttribute('aria-live')).toBe('off');
  });

  it('renders 00:00 immediately for a target in the past', () => {
    render(<Countdown targetTime={BASE - 1_000} />);
    expect(screen.getByText('00:00').className).toContain('text-error');
  });

  it('T17 AC-4: N>=3 concurrent Countdowns share exactly one 1 Hz interval and decrement independently', () => {
    const onCompleteA = vi.fn();
    const onCompleteB = vi.fn();
    const onCompleteC = vi.fn();
    const intervalSpy = vi.spyOn(globalThis, 'setInterval');
    render(
      <div>
        <Countdown targetTime={BASE + 90_000} className="a" onComplete={onCompleteA} />
        <Countdown targetTime={BASE + 45_000} className="b" onComplete={onCompleteB} />
        <Countdown targetTime={BASE + 10_000} className="c" onComplete={onCompleteC} />
      </div>,
    );
    // Three consumers, ONE shared interval at 1000 ms (the guest-status shape).
    expect(intervalSpy).toHaveBeenCalledTimes(1);
    expect(intervalSpy.mock.calls[0][1]).toBe(1000);
    tick(1);
    expect(screen.getByText('01:29')).toBeTruthy();
    expect(screen.getByText('00:44')).toBeTruthy();
    expect(screen.getByText('00:09')).toBeTruthy();
    // C reaches zero first and fires its own onComplete exactly once; A and B
    // keep ticking on the same shared interval.
    tick(9);
    expect(onCompleteC).toHaveBeenCalledTimes(1);
    expect(onCompleteA).not.toHaveBeenCalled();
    expect(onCompleteB).not.toHaveBeenCalled();
    expect(screen.getByText('01:20')).toBeTruthy();
    expect(screen.getByText('00:35')).toBeTruthy();
    // B reaches zero at t=45s on the shared interval.
    tick(35);
    expect(onCompleteB).toHaveBeenCalledTimes(1);
    expect(onCompleteA).not.toHaveBeenCalled();
    expect(screen.getByText('00:45')).toBeTruthy();
    // A reaches zero at t=90s; the shared ticker then dies with the last subscriber.
    tick(45);
    expect(onCompleteA).toHaveBeenCalledTimes(1);
    expect(onCompleteA).toHaveBeenCalledTimes(1);
    expect(onCompleteB).toHaveBeenCalledTimes(1);
    expect(onCompleteC).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
    expect(intervalSpy).toHaveBeenCalledTimes(1);
  });
});
