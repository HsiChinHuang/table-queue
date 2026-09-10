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
});
