// @vitest-environment jsdom
/**
 * ConnectionBanner, useConnection, ConnectionProvider and useConnectionContext (F-15).
 * The banner only appears at the 3-failure threshold (and for the 3s "recovered" message);
 * the provider is what keeps ONE counter across the tree - the bug StaffLayout had in F-06
 * (DEF-F06-1 class), so it is asserted explicitly here.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import {
  ConnectionBanner,
  ConnectionProvider,
  useConnection,
  useConnectionContext,
} from './ConnectionBanner';

const ROOT = () => document.querySelector('[role="alert"]');

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('ConnectionBanner presentation', () => {
  it('stays hidden below the threshold', () => {
    const { container } = render(<ConnectionBanner failureCount={2} />);
    expect(container.textContent).toBe('');
    expect(ROOT()).toBeNull();
  });

  it('shows the retry banner at the threshold', () => {
    render(<ConnectionBanner failureCount={3} />);
    expect(ROOT()?.textContent).toContain('Connection lost. Retrying...');
    expect(ROOT()?.className).toContain('fixed');
    expect(ROOT()?.getAttribute('aria-live')).toBe('assertive');
  });

  it('shows the Retry button only when a handler is provided', () => {
    const { unmount } = render(<ConnectionBanner failureCount={4} />);
    expect(screen.queryByText('Retry')).toBeNull();
    unmount();
    const onRetry = vi.fn();
    render(<ConnectionBanner failureCount={4} onRetry={onRetry} />);
    fireEvent.click(screen.getByLabelText('Retry connection'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('appends className to the fixed root', () => {
    render(<ConnectionBanner failureCount={5} className="top-10" />);
    expect(ROOT()?.className).toContain('top-10');
  });

  it('shows the recovered message once failures drop to zero', () => {
    const { rerender } = render(<ConnectionBanner failureCount={3} />);
    rerender(<ConnectionBanner failureCount={0} />);
    expect(ROOT()?.textContent).toContain('Updated just now');
    act(() => void vi.advanceTimersByTime(3_000));
    expect(ROOT()).toBeNull();
  });
});

describe('useConnection', () => {
  interface Probe {
    failureCount: number;
    isDisconnected: boolean;
    isRecovered: boolean;
    incrementFailure: () => void;
    resetFailure: () => void;
  }

  function Harness({ onRetry, probe }: { onRetry?: () => void; probe: (p: Probe) => void }) {
    const value = useConnection(onRetry);
    probe(value);
    return React.createElement(
      'div',
      null,
      React.createElement('span', { 'data-testid': 'count' }, String(value.failureCount)),
      React.createElement('span', { 'data-testid': 'disconnected' }, String(value.isDisconnected)),
      React.createElement('button', { onClick: value.incrementFailure }, 'fail'),
      React.createElement('button', { onClick: value.resetFailure }, 'recover'),
    );
  }

  const fail = () => fireEvent.click(screen.getByText('fail'));
  const recover = () => fireEvent.click(screen.getByText('recover'));

  it('crosses the threshold at three failures', () => {
    let last!: Probe;
    render(React.createElement(Harness, { probe: (p: Probe) => (last = p) }));
    expect(last.isDisconnected).toBe(false);
    fail();
    fail();
    expect(screen.getByTestId('count').textContent).toBe('2');
    expect(screen.getByTestId('disconnected').textContent).toBe('false');
    fail();
    expect(screen.getByTestId('disconnected').textContent).toBe('true');
  });

  it('resets the counter and flags recovery', () => {
    let last!: Probe;
    render(React.createElement(Harness, { probe: (p: Probe) => (last = p) }));
    fail();
    fail();
    fail();
    recover();
    expect(last.failureCount).toBe(0);
    expect(last.isDisconnected).toBe(false);
    expect(last.isRecovered).toBe(true);
    act(() => void vi.advanceTimersByTime(3_000));
    expect(last.isRecovered).toBe(false);
  });

  it('calls onRetry only when there was something to recover from', () => {
    const onRetry = vi.fn();
    render(React.createElement(Harness, { onRetry, probe: () => {} }));
    recover();
    expect(onRetry).not.toHaveBeenCalled();
    fail();
    recover();
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe('ConnectionProvider', () => {
  function Consumer() {
    const { failureCount, incrementFailure } = useConnectionContext();
    return React.createElement(
      'div',
      null,
      React.createElement('span', { 'data-testid': 'a' }, String(failureCount)),
      React.createElement('button', { onClick: incrementFailure }, 'inc'),
    );
  }

  function SecondConsumer() {
    const { failureCount } = useConnectionContext();
    return React.createElement('span', { 'data-testid': 'b' }, String(failureCount));
  }

  it('shares one counter between every consumer', () => {
    render(
      React.createElement(
        ConnectionProvider,
        null,
        React.createElement(Consumer, null),
        React.createElement(SecondConsumer, null),
      ),
    );
    fireEvent.click(screen.getByText('inc'));
    fireEvent.click(screen.getByText('inc'));
    expect(screen.getByTestId('a').textContent).toBe('2');
    expect(screen.getByTestId('b').textContent).toBe('2');
  });

  it('throws a helpful error when the context is used outside the provider', () => {
    function Orphan() {
      useConnectionContext();
      return null;
    }
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(React.createElement(Orphan, null))).toThrow(
      'useConnectionContext must be used within ConnectionProvider',
    );
    spy.mockRestore();
  });
});
