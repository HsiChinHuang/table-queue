// @vitest-environment jsdom
/**
 * StaffLayout (F-15): the auth guard, the nav targets, logout clearing the token, Outlet
 * rendering and the DEV badge in dev builds.
 *
 * The layout reads its session from the REACT HOOK `@/api/staffStore` (note: the kit has both
 * `@/api/staffStore` and the zustand store in `@/stores/staffStore`; StaffLayout imports the
 * former, so that is the module mocked here).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';

const { destroySession } = vi.hoisted(() => ({ destroySession: vi.fn() }));
let session: { token: string | null; expiresAt: number | null } = {
  token: 'tok-12345678',
  expiresAt: null,
};

vi.mock('@/stores/staffStore', () => ({
  destroySession,
  // Real predicate (mirrors the store's export) so the layout's own expiry check
  // is exercised; the watcher/rehydrate guard that live in the real module are out
  // of scope here - this file pins the layout's redirect decision.
  isSessionExpired: (s: { token: string | null; expiresAt: number | null }) =>
    s.token !== null && s.expiresAt !== null && Date.now() >= s.expiresAt,
}));

vi.mock('@/api/staffStore', () => ({
  useStaffStore: () => ({
    token: session.token,
    expiresAt: session.expiresAt,
  }),
}));

import StaffLayout from './StaffLayout';

function renderAt(path: string) {
  const router = createMemoryRouter(
    [
      {
        element: <StaffLayout />,
        children: [
          { path: '/staff/board', element: <div data-testid="outlet">STAFF CHILD</div> },
          { path: '/staff/login', element: <div>LOGIN SCREEN</div> },
          { path: '/staff/waitlist', element: <div>WAITLIST SCREEN</div> },
          { path: '/staff/tables', element: <div>TABLES SCREEN</div> },
          { path: '/admin/settings', element: <div>SETTINGS SCREEN</div> },
        ],
      },
    ],
    { initialEntries: [path] },
  );
  return render(<RouterProvider router={router} />);
}

afterEach(() => {
  cleanup();
  destroySession.mockClear();
  session = { token: 'tok-12345678', expiresAt: null };
  vi.unstubAllEnvs();
});

describe('auth guard', () => {
  it('redirects an anonymous visitor to the login screen', () => {
    session = { token: null, expiresAt: null };
    renderAt('/staff/board');
    expect(screen.getByText('LOGIN SCREEN')).toBeTruthy();
    expect(screen.queryByTestId('outlet')).toBeNull();
  });

  it('renders the child once a token exists', () => {
    renderAt('/staff/board');
    expect(screen.getByTestId('outlet').textContent).toBe('STAFF CHILD');
    expect(screen.queryByText('LOGIN SCREEN')).toBeNull();
  });

  it('T17: renders the child for a token with a future known expiry', () => {
    session = { token: 'tok-12345678', expiresAt: Date.now() + 3_600_000 };
    renderAt('/staff/board');
    expect(screen.getByTestId('outlet').textContent).toBe('STAFF CHILD');
    expect(screen.queryByText('LOGIN SCREEN')).toBeNull();
  });

  it('T17: treats a token whose known expiry has passed as logged out (redirect)', () => {
    session = { token: 'tok-12345678', expiresAt: Date.now() - 1_000 };
    renderAt('/staff/board');
    expect(screen.getByText('LOGIN SCREEN')).toBeTruthy();
    expect(screen.queryByTestId('outlet')).toBeNull();
  });

  it('T17: keeps the login route reachable for an expired token', () => {
    session = { token: 'tok-12345678', expiresAt: Date.now() - 1_000 };
    renderAt('/staff/login');
    expect(screen.getByText('LOGIN SCREEN')).toBeTruthy();
  });

  it('leaves the login route itself reachable without a token', () => {
    session = { token: null, expiresAt: null };
    renderAt('/staff/login');
    expect(screen.getByText('LOGIN SCREEN')).toBeTruthy();
  });
});

describe('chrome', () => {
  it('links to the three staff destinations', () => {
    renderAt('/staff/board');
    expect(screen.getByRole('link', { name: 'Waitlist' }).getAttribute('href')).toBe(
      '/staff/waitlist',
    );
    expect(screen.getByRole('link', { name: 'Tables' }).getAttribute('href')).toBe('/staff/tables');
    expect(screen.getByRole('link', { name: 'Settings' }).getAttribute('href')).toBe(
      '/admin/settings',
    );
  });

  it('clears the session when Log out is clicked', () => {
    renderAt('/staff/board');
    fireEvent.click(screen.getByLabelText('Log out'));
    expect(destroySession).toHaveBeenCalledTimes(1);
  });

  it('shows the brand heading and the main landmark', () => {
    renderAt('/staff/board');
    expect(screen.getByRole('heading', { level: 1, name: 'TableQueue Staff' })).toBeTruthy();
    expect(screen.getByRole('main')).toBeTruthy();
  });

  it('renders the DEV badge in dev builds and hides it in production', () => {
    vi.stubEnv('DEV', true);
    const { unmount } = renderAt('/staff/board');
    expect(screen.getByText('DEV | Mock Data')).toBeTruthy();
    unmount();
    cleanup();
    vi.stubEnv('DEV', false);
    renderAt('/staff/board');
    expect(screen.queryByText('DEV | Mock Data')).toBeNull();
  });

  it('DEFECT DEF-F15-3: no ConnectionBanner wiring and no skip link in the staff chrome', () => {
    // design-briefs.md wants the connection banner mounted in the staff shell (it is only used
    // by pages today) and a skip link target; neither exists in StaffLayout. Recorded, not
    // patched (F-06 owns layouts/StaffLayout.tsx).
    renderAt('/staff/board');
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByRole('link', { name: /skip to content/i })).toBeNull();
  });
});
