// @vitest-environment jsdom
/**
 * DevBadge (F-15): renders the DEV | Mock Data marker under DEV and nothing otherwise.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import DevBadge from './DevBadge';

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe('DevBadge', () => {
  it('renders the mock-data marker in dev builds', () => {
    vi.stubEnv('DEV', true);
    const { container } = render(<DevBadge />);
    expect(container.textContent).toBe('DEV | Mock Data');
  });

  it('renders nothing in production builds', () => {
    vi.stubEnv('DEV', false);
    const { container } = render(<DevBadge />);
    expect(container.textContent).toBe('');
  });
});
