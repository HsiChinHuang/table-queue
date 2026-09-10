// @vitest-environment jsdom
/**
 * WaitlistCard (F-15): identity rows, the status-conditional action set, the Countdown only
 * for a CALLED entry with a target time, the wait-minutes line for other statuses, the note
 * line, and every callback prop firing.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { WaitlistCard } from './WaitlistCard';

const entry = {
  id: 1,
  queueNumber: 'A001',
  name: 'Alice Chen',
  phone: '0912-345-678',
  partySize: 4,
  status: 'WAITING' as const,
  note: 'Window seat',
  waitMinutes: 12,
};

const withStatus = (status: 'WAITING' | 'CALLED' | 'NO_SHOW', extra: Record<string, unknown> = {}) =>
  ({ ...entry, status, ...extra }) as never;

afterEach(cleanup);

const click = (label: string) => fireEvent.click(screen.getByLabelText(label));
const present = (text: string) => screen.queryByText(text) !== null;

describe('identity', () => {
  it('shows queue number, name, party size, phone and status', () => {
    render(<WaitlistCard entry={withStatus('WAITING')} />);
    expect(screen.getByText('A001')).toBeTruthy();
    expect(screen.getByText('Alice Chen')).toBeTruthy();
    expect(screen.getByText('· 4 pax')).toBeTruthy();
    expect(screen.getByText('0912-345-678')).toBeTruthy();
    expect(screen.getByText('Waiting')).toBeTruthy();
  });

  it('shows the note only when one exists', () => {
    const { unmount } = render(<WaitlistCard entry={withStatus('WAITING')} />);
    expect(present('Window seat')).toBe(true);
    unmount();
    const { container } = render(
      <WaitlistCard entry={{ ...entry, note: undefined } as never} />,
    );
    expect(container.textContent?.includes('Window seat')).toBe(false);
  });
});

describe('time rows', () => {
  it('shows the wait minutes line for a WAITING entry', () => {
    render(<WaitlistCard entry={withStatus('WAITING')} />);
    expect(screen.getByText('Waiting 12 min')).toBeTruthy();
  });

  it('replaces the wait line with a live Countdown for a CALLED entry', () => {
    render(<WaitlistCard entry={withStatus('CALLED', { targetTime: Date.now() + 60_000 })} />);
    expect(screen.getByText('01:00')).toBeTruthy();
    expect(present('Waiting 12 min')).toBe(false);
  });
});

describe('action set per status', () => {
  it('WAITING offers Call, Seat and Cancel but not No-show or Restore', () => {
    render(<WaitlistCard entry={withStatus('WAITING')} onCall={vi.fn()} onSeat={vi.fn()} onNoShow={vi.fn()} onRestore={vi.fn()} onCancel={vi.fn()} />);
    expect(present('Call')).toBe(true);
    expect(present('Seat')).toBe(true);
    expect(present('Cancel')).toBe(true);
    expect(present('No-show')).toBe(false);
    expect(present('Restore')).toBe(false);
  });

  it('CALLED adds No-show and Revert', () => {
    render(
      <WaitlistCard
        entry={withStatus('CALLED', { targetTime: Date.now() + 60_000 })}
        onCall={vi.fn()}
        onSeat={vi.fn()}
        onNoShow={vi.fn()}
        onRevert={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(present('Call')).toBe(false);
    expect(present('No-show')).toBe(true);
    expect(present('Revert')).toBe(true);
  });

  it('NO_SHOW offers only Restore', () => {
    render(<WaitlistCard entry={withStatus('NO_SHOW')} onRestore={vi.fn()} onCancel={vi.fn()} onSeat={vi.fn()} />);
    expect(present('Restore')).toBe(true);
    expect(present('Cancel')).toBe(false);
    expect(present('Seat')).toBe(false);
  });

  it('hides every action when no callback is passed', () => {
    render(<WaitlistCard entry={withStatus('WAITING')} />);
    expect(screen.queryAllByRole('button').length).toBe(0);
  });
});

describe('callbacks', () => {
  it('fires each handler with the buttons the entry exposes', () => {
    const onCall = vi.fn();
    const onSeat = vi.fn();
    const onCancel = vi.fn();
    const onEdit = vi.fn();
    render(<WaitlistCard entry={withStatus('WAITING')} onCall={onCall} onSeat={onSeat} onCancel={onCancel} onEdit={onEdit} />);
    click('Call Alice Chen');
    expect(onCall).toHaveBeenCalledTimes(1);
    click('Seat Alice Chen');
    expect(onSeat).toHaveBeenCalledTimes(1);
    click('Cancel Alice Chen');
    expect(onCancel).toHaveBeenCalledTimes(1);
    click('Edit Alice Chen');
    expect(onEdit).toHaveBeenCalledTimes(1);
  });

  it('fires No-show, Revert and Restore on the matching statuses', () => {
    const onNoShow = vi.fn();
    const onRevert = vi.fn();
    const { unmount } = render(
      <WaitlistCard
        entry={withStatus('CALLED', { targetTime: Date.now() + 60_000 })}
        onNoShow={onNoShow}
        onRevert={onRevert}
      />,
    );
    click('Mark Alice Chen as no-show');
    expect(onNoShow).toHaveBeenCalledTimes(1);
    click('Revert call for Alice Chen');
    expect(onRevert).toHaveBeenCalledTimes(1);
    unmount();
    const onRestore = vi.fn();
    render(<WaitlistCard entry={withStatus('NO_SHOW')} onRestore={onRestore} />);
    click('Restore Alice Chen');
    expect(onRestore).toHaveBeenCalledTimes(1);
  });
});
