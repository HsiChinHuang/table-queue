// @vitest-environment jsdom
/**
 * EmptyState (F-15): icon/title/description/action slots, the status role, and className
 * pass-through.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { EmptyState } from './EmptyState';

afterEach(cleanup);

describe('EmptyState', () => {
  it('renders title, description and icon', () => {
    const { container } = render(
      <EmptyState icon={<span data-testid="icon">🪑</span>} title="No tables" description="Add a table to get started." />,
    );
    expect(screen.getByText('No tables')).toBeTruthy();
    expect(screen.getByText('Add a table to get started.')).toBeTruthy();
    const iconWrap = container.querySelector('[aria-hidden="true"]');
    expect(iconWrap?.textContent).toBe('🪑');
  });

  it('announces itself as a live status region', () => {
    render(<EmptyState icon={<span>i</span>} title="T" description="D" />);
    const region = screen.getByRole('status');
    expect(region.getAttribute('aria-live')).toBe('polite');
  });

  it('omits the action slot when none is given and renders it otherwise', () => {
    const onClick = vi.fn();
    const { unmount, container } = render(
      <EmptyState icon={<span>i</span>} title="T" description="D" />,
    );
    expect(container.querySelector('div > div:last-child > button')).toBeNull();
    unmount();
    render(
      <EmptyState
        icon={<span>i</span>}
        title="T"
        description="D"
        action={<button onClick={onClick}>Add table</button>}
      />,
    );
    fireEvent.click(screen.getByText('Add table'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('appends className to the root', () => {
    render(<EmptyState icon={<span>i</span>} title="T" description="D" className="py-24" />);
    expect(screen.getByRole('status').className).toContain('py-24');
  });
});
