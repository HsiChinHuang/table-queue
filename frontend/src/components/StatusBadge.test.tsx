// @vitest-environment jsdom
/**
 * StatusBadge (F-15): every waitlist and table status has a label and a colour class, the
 * three size variants differ, and className is appended.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { StatusBadge } from './StatusBadge';

const cases: Array<[string, string, string]> = [
  ['WAITING', 'Waiting', 'bg-WAITING'],
  ['CALLED', 'Called', 'bg-called'],
  ['SEATED', 'Seated', 'bg-SEATED'],
  ['NO_SHOW', 'No-show', 'bg-NO_SHOW'],
  ['CANCELLED', 'Cancelled', 'bg-CANCELLED'],
  ['DONE', 'Done', 'bg-DONE'],
  ['AVAILABLE', 'Available', 'bg-AVAILABLE'],
  ['OCCUPIED', 'Occupied', 'bg-OCCUPIED'],
  ['CLEANING', 'Cleaning', 'bg-CLEANING'],
];

afterEach(cleanup);

describe('StatusBadge', () => {
  it('renders a label and colour class for all nine statuses', () => {
    for (const [status, label, colorClass] of cases) {
      const { unmount } = render(<StatusBadge status={status as never} />);
      const el = document.querySelector('span');
      expect(el?.textContent).toBe(label);
      expect(el?.className).toContain(colorClass);
      expect(el?.className).toContain('rounded-full');
      unmount();
    }
  });

  it('defaults to the md size', () => {
    render(<StatusBadge status="WAITING" />);
    expect(document.querySelector('span')?.className).toContain('text-sm');
  });

  it('supports sm and lg sizes', () => {
    const { unmount } = render(<StatusBadge status="SEATED" size="sm" />);
    expect(document.querySelector('span')?.className).toContain('text-xs');
    unmount();
    render(<StatusBadge status="SEATED" size="lg" />);
    expect(document.querySelector('span')?.className).toContain('text-base');
  });

  it('appends className and announces politely', () => {
    render(<StatusBadge status="CALLED" className="ml-2" />);
    const el = document.querySelector('span');
    expect(el?.className).toContain('ml-2');
    expect(el?.getAttribute('aria-live')).toBe('polite');
  });
});
