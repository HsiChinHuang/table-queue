// @vitest-environment jsdom
/**
 * PublicLayout (F-15): renders the routed child, the brand header/footer landmarks and — only
 * in dev builds — the DEV badge (AC-10 second half).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import PublicLayout from './PublicLayout';

function renderLayout(path = '/join/branch-001') {
  const router = createMemoryRouter(
    [
      {
        path: '/join',
        element: <PublicLayout />,
        children: [{ path: ':branchId', element: <div data-testid="outlet">PUBLIC CHILD</div> }],
      },
    ],
    { initialEntries: [path] },
  );
  return render(<RouterProvider router={router} />);
}

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

describe('PublicLayout', () => {
  it('renders the routed child through Outlet', () => {
    renderLayout();
    expect(screen.getByTestId('outlet').textContent).toBe('PUBLIC CHILD');
  });

  it('shows the brand header and the copyright footer', () => {
    renderLayout();
    expect(screen.getByRole('heading', { level: 1, name: 'TableQueue' })).toBeTruthy();
    expect(screen.getByText('Restaurant Waitlist Manager')).toBeTruthy();
    expect(screen.getByRole('contentinfo').textContent).toContain(`${new Date().getFullYear()} TableQueue`);
  });

  it('exposes the banner/main landmarks', () => {
    renderLayout();
    expect(screen.getByRole('banner')).toBeTruthy();
    expect(screen.getByRole('main')).toBeTruthy();
  });

  it('renders the DEV badge in dev builds', () => {
    vi.stubEnv('DEV', true);
    renderLayout();
    expect(screen.getByText('DEV | Mock Data')).toBeTruthy();
  });

  it('hides the DEV badge in production builds', () => {
    vi.stubEnv('DEV', false);
    renderLayout();
    expect(screen.queryByText('DEV | Mock Data')).toBeNull();
  });

  it('DEFECT DEF-F15-2: no skip link / #main-content target on the public layout', () => {
    // design-briefs.md lists a skip-to-content link as a shared layout requirement; StaffLayout
    // has one, PublicLayout does not. Recorded, not patched here (F-05 owns layouts/).
    renderLayout();
    expect(screen.queryByRole('link', { name: /skip to content/i })).toBeNull();
    expect(document.getElementById('main-content')).toBeNull();
  });
});
