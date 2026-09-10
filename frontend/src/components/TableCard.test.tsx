// @vitest-environment jsdom
/**
 * TableCard (F-15): label/capacity/occupant rows, the clickable-vs-static role per status,
 * keyboard activation, and the Release action for occupied tables.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { TableCard } from './TableCard';

const table = {
  id: 7,
  label: 'B2',
  capacity: 6,
  status: 'OCCUPIED' as const,
  occupiedBy: { queueNumber: 'A001', partySize: 4, targetTime: Date.now() + 60_000 },
};

const asTable = (extra: Record<string, unknown> = {}) =>
  ({ ...table, ...extra }) as never;

afterEach(cleanup);

describe('rows', () => {
  it('shows label, capacity and the occupant queue number', () => {
    render(<TableCard table={asTable()} />);
    expect(screen.getByText('B2')).toBeTruthy();
    expect(screen.getByText('6 pax')).toBeTruthy();
    expect(screen.getByText('A001 · 4 pax')).toBeTruthy();
    expect(screen.getByText('Occupied')).toBeTruthy();
    expect(screen.getByText('01:00')).toBeTruthy();
  });

  it('shows Available for an empty table and no Release button', () => {
    const { container } = render(
      <TableCard table={asTable({ status: 'AVAILABLE', occupiedBy: undefined })} onRelease={vi.fn()} />,
    );
    // 'Available' appears twice by design: the StatusBadge label and the status paragraph.
    expect(container.querySelector('p')?.textContent).toBe('Available');
    expect(screen.queryByText('Release Table')).toBeNull();
  });

  it('shows the cleaning line for CLEANING', () => {
    render(<TableCard table={asTable({ status: 'CLEANING', occupiedBy: undefined })} />);
    expect(screen.getByText('Currently cleaning')).toBeTruthy();
  });

  it('falls back to the plain status line when an occupied table has no occupant', () => {
    const { container } = render(<TableCard table={asTable({ occupiedBy: undefined })} />);
    expect(container.querySelector('p')?.textContent).toBe('Available');
  });
});

describe('interaction', () => {
  it('is a button while free and an article when occupied', () => {
    const { unmount } = render(<TableCard table={asTable({ status: 'AVAILABLE', occupiedBy: undefined })} />);
    expect(screen.getByRole('button', { name: 'Table B2, 6 pax, available' })).toBeTruthy();
    unmount();
    render(<TableCard table={asTable()} />);
    expect(screen.getByRole('article', { name: 'Table B2, 6 pax, occupied' })).toBeTruthy();
  });

  it('calls onClick on click and on Enter for a free table', () => {
    const onClick = vi.fn();
    render(<TableCard table={asTable({ status: 'AVAILABLE', occupiedBy: undefined })} onClick={onClick} />);
    const card = screen.getByRole('button');
    fireEvent.click(card);
    expect(onClick).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(card, { key: 'Enter' });
    expect(onClick).toHaveBeenCalledTimes(2);
    fireEvent.keyDown(card, { key: ' ' });
    expect(onClick).toHaveBeenCalledTimes(3);
  });

  it('ignores clicks on an occupied table', () => {
    const onClick = vi.fn();
    render(<TableCard table={asTable()} onClick={onClick} />);
    fireEvent.click(screen.getByRole('article'));
    expect(onClick).not.toHaveBeenCalled();
  });

  it('releases without triggering the card click', () => {
    const onClick = vi.fn();
    const onRelease = vi.fn();
    render(<TableCard table={asTable()} onClick={onClick} onRelease={onRelease} />);
    fireEvent.click(screen.getByLabelText('Release table B2'));
    expect(onRelease).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });
});
