// @vitest-environment jsdom
/**
 * Tests for LoginPage.
 * F-11: tokenStorageFor, redirect guard, PIN submit, AUTH_INVALID_PIN / AUTH_RATE_LIMITED copy,
 * remember-me storage selection, store update and navigation to /staff/waitlist.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/react';
import type { RenderResult } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage, { tokenStorageFor, STAFF_TOKEN_KEY } from './LoginPage';
import { login } from '@/api/auth';
import { staffStore } from '@/stores/staffStore';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  changePin: vi.fn(),
}));

const loginMock = vi.mocked(login);

let view: RenderResult | null = null;

afterEach(() => {
  view?.unmount();
  view = null;
  loginMock.mockReset();
  mockNavigate.mockReset();
  staffStore.setState({ token: null });
  localStorage.clear();
  sessionStorage.clear();
});

function renderPage(): RenderResult {
  view = render(
    <MemoryRouter initialEntries={['/staff/login']}>
      <LoginPage />
    </MemoryRouter>
  );
  return view;
}

function successfulLogin() {
  loginMock.mockResolvedValue({
    token: 'test-token',
    staff_id: 'staff-1',
    expires_at: '2026-01-01T00:00:00Z',
  });
}

function failedLogin(code: string) {
  loginMock.mockRejectedValue({ code });
}

async function submitPin(pin: string, uncheckRemember = false) {
  const page = renderPage();
  fireEvent.change(page.getByPlaceholderText('Enter your PIN'), { target: { value: pin } });
  if (uncheckRemember) {
    fireEvent.click(page.getByRole('checkbox', { name: /remember me/i }));
  }
  fireEvent.click(page.getByRole('button', { name: /login/i }));
  await waitFor(() => expect(loginMock).toHaveBeenCalled());
  return page;
}

describe('tokenStorageFor', () => {
  it('returns localStorage when remember is true', () => {
    expect(tokenStorageFor(true)).toBe('localStorage');
  });

  it('returns sessionStorage when remember is false', () => {
    expect(tokenStorageFor(false)).toBe('sessionStorage');
  });
});

describe('LoginPage form', () => {
  it('renders a masked numeric PIN input', () => {
    const page = renderPage();
    const pin = page.getByPlaceholderText('Enter your PIN');
    expect(pin.getAttribute('type')).toBe('password');
    expect(pin.getAttribute('inputmode')).toBe('numeric');
  });

  it('checks remember-me by default', () => {
    const page = renderPage();
    expect(page.getByRole('checkbox', { name: /remember me/i }).hasAttribute('checked')).toBe(true);
  });

  it('sends the PIN to the login endpoint', async () => {
    successfulLogin();
    await submitPin('1234');
    expect(loginMock).toHaveBeenCalledWith({ pin: '1234' });
  });
});

describe('LoginPage success path', () => {
  it('stores the token in localStorage when remember-me is checked', async () => {
    successfulLogin();
    await submitPin('1234');
    await waitFor(() => expect(localStorage.getItem(STAFF_TOKEN_KEY)).toBe('test-token'));
    expect(sessionStorage.getItem(STAFF_TOKEN_KEY)).toBeNull();
  });

  it('stores the token in sessionStorage when remember-me is unchecked', async () => {
    successfulLogin();
    await submitPin('1234', true);
    await waitFor(() => expect(sessionStorage.getItem(STAFF_TOKEN_KEY)).toBe('test-token'));
    expect(localStorage.getItem(STAFF_TOKEN_KEY)).toBeNull();
  });

  it('updates the staff store and navigates to /staff/waitlist', async () => {
    successfulLogin();
    await submitPin('1234');
    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith('/staff/waitlist', { replace: true })
    );
    expect(staffStore.getState().token).toBe('test-token');
  });
});

describe('LoginPage error paths', () => {
  it('shows "Invalid PIN." for AUTH_INVALID_PIN', async () => {
    failedLogin('AUTH_INVALID_PIN');
    const page = await submitPin('0000');
    await waitFor(() => expect(page.getByRole('alert').textContent).toBe('Invalid PIN.'));
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('shows the rate-limit copy for AUTH_RATE_LIMITED', async () => {
    failedLogin('AUTH_RATE_LIMITED');
    const page = await submitPin('0000');
    await waitFor(() =>
      expect(page.getByRole('alert').textContent).toBe('Too many attempts. Please try again later.')
    );
  });

  it('shows a generic error for unexpected failures', async () => {
    failedLogin('NETWORK_ERROR');
    const page = await submitPin('0000');
    await waitFor(() => expect(page.getByRole('alert').textContent).not.toBe(''));
    expect(page.getByRole('alert').textContent).not.toBe('Invalid PIN.');
  });
});

describe('LoginPage redirect guard', () => {
  it('redirects already-authenticated staff to /staff/waitlist', async () => {
    staffStore.setState({ token: 'existing-token' });
    const page = renderPage();
    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith('/staff/waitlist', { replace: true })
    );
    expect(page.queryByPlaceholderText('Enter your PIN')).toBeNull();
    expect(loginMock).not.toHaveBeenCalled();
  });
});
