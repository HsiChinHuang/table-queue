// @vitest-environment jsdom
/**
 * ConfirmDialog (F-15): open/closed rendering, default vs custom labels, the confirm/cancel
 * callback contract (both handlers also close), the danger variant styling and Escape handling.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { ConfirmDialog } from './ConfirmDialog';

afterEach(cleanup);

const base = {
  title: 'Release table',
  description: 'The guest will be moved to the end of the list.',
};

describe('rendering', () => {
  it('renders nothing while closed', () => {
    const { container } = render(
      <ConfirmDialog open={false} onClose={vi.fn()} onConfirm={vi.fn()} {...base} />,
    );
    expect(container.textContent).toBe('');
  });

  it('shows the title, description and default Confirm/Cancel labels', () => {
    render(<ConfirmDialog open onClose={vi.fn()} onConfirm={vi.fn()} {...base} />);
    expect(screen.getByText('Release table')).toBeTruthy();
    expect(screen.getByText('The guest will be moved to the end of the list.')).toBeTruthy();
    expect(screen.getByText('Confirm')).toBeTruthy();
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('omits the description when none is given and honours custom labels', () => {
    render(
      <ConfirmDialog
        open
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        title="Reset data"
        confirmLabel="Reset Data"
        cancelLabel="Keep data"
      />,
    );
    expect(screen.queryByText('The guest will be moved to the end of the list.')).toBeNull();
    expect(screen.getByText('Reset Data')).toBeTruthy();
    expect(screen.getByText('Keep data')).toBeTruthy();
    expect(screen.queryByText('Confirm')).toBeNull();
  });
});

describe('callbacks', () => {
  it('confirms and closes', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(<ConfirmDialog open onClose={onClose} onConfirm={onConfirm} {...base} />);
    fireEvent.click(screen.getByText('Confirm'));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('cancels, reports the cancellation and closes', () => {
    const onCancel = vi.fn();
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog open onClose={onClose} onConfirm={onConfirm} onCancel={onCancel} {...base} />,
    );
    fireEvent.click(screen.getByText('Cancel'));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes without a cancel handler present', () => {
    const onClose = vi.fn();
    render(<ConfirmDialog open onClose={onClose} onConfirm={vi.fn()} {...base} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('treats Escape as a cancel', () => {
    const onCancel = vi.fn();
    const onClose = vi.fn();
    render(
      <ConfirmDialog open onClose={onClose} onConfirm={vi.fn()} onCancel={onCancel} {...base} />,
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('ignores Escape while closed', () => {
    const onCancel = vi.fn();
    render(
      <ConfirmDialog open={false} onClose={vi.fn()} onConfirm={vi.fn()} onCancel={onCancel} {...base} />,
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCancel).not.toHaveBeenCalled();
  });
});

describe('variant', () => {
  it('uses the danger colour for the confirm button', () => {
    render(<ConfirmDialog open onClose={vi.fn()} onConfirm={vi.fn()} variant="danger" {...base} />);
    expect(screen.getByText('Confirm').className).toContain('bg-NO_SHOW');
  });

  it('uses the neutral colour by default', () => {
    render(<ConfirmDialog open onClose={vi.fn()} onConfirm={vi.fn()} {...base} />);
    const cls = screen.getByText('Confirm').className;
    expect(cls).not.toContain('bg-NO_SHOW');
  });
});
