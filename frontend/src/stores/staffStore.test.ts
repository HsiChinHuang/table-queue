// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { staffStore, destroySession, isSessionExpired } from './staffStore';
import { login } from '@/api/auth';

describe('staffStore', () => {
  beforeEach(() => {
    staffStore.setState({ token: null, soundEnabled: true });
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
    staffStore.getState().setToken(null);
    staffStore.getState().setExpiresAt(null);
    localStorage.clear();
    sessionStorage.clear();
  });

  it('has initial state', () => {
    const state = staffStore.getState();
    expect(state.token).toBe(null);
    expect(state.expiresAt).toBe(null);
    expect(state.soundEnabled).toBe(true);
  });

  it('setToken updates token', () => {
    staffStore.getState().setToken('test-token');
    expect(staffStore.getState().token).toBe('test-token');
  });

  it('logout clears token', () => {
    staffStore.getState().setToken('test-token');
    staffStore.getState().logout();
    expect(staffStore.getState().token).toBe(null);
  });

  it('setSoundEnabled updates soundEnabled', () => {
    staffStore.getState().setSoundEnabled(false);
    expect(staffStore.getState().soundEnabled).toBe(false);
  });

  it('persists to localStorage', () => {
    staffStore.getState().setToken('persisted-token');
    staffStore.getState().setSoundEnabled(false);
    
    const stored = JSON.parse(localStorage.getItem('staff-storage') || '{}');
    expect(stored.state.token).toBe('persisted-token');
    expect(stored.state.soundEnabled).toBe(false);
  });

  it('rehydrates from localStorage', async () => {
    localStorage.setItem('staff-storage', JSON.stringify({
      state: { token: 'rehydrated-token', soundEnabled: false }
    }));
    
    await staffStore.persist.rehydrate();
    
    const state = staffStore.getState();
    expect(state.token).toBe('rehydrated-token');
    expect(state.soundEnabled).toBe(false);
  });
});

describe('T17 expiresAt lifecycle (AC-1)', () => {
  it('holds expiresAt alongside the token and persists it in the staff-storage envelope', () => {
    staffStore.getState().setToken('expiring-token');
    const expiresAt = 1_700_003_600_000;
    staffStore.getState().setExpiresAt(expiresAt);
    const state = staffStore.getState();
    expect(state.token).toBe('expiring-token');
    expect(state.expiresAt).toBe(expiresAt);
    const stored = JSON.parse(localStorage.getItem('staff-storage') || '{}');
    expect(stored.state.token).toBe('expiring-token');
    expect(stored.state.expiresAt).toBe(expiresAt);
  });

  it('rehydrates expiresAt together with the token after a reload', async () => {
    const expiresAt = Date.now() + 3_600_000; // still live: the hydrated guard must not fire
    localStorage.setItem('staff-storage', JSON.stringify({
      state: { token: 'rehydrated-expiring-token', expiresAt, soundEnabled: true },
    }));
    await staffStore.persist.rehydrate();
    expect(staffStore.getState().token).toBe('rehydrated-expiring-token');
    expect(staffStore.getState().expiresAt).toBe(expiresAt);
  });

  it('login() records expiresAt = Date.now() + expires_in * 1000 and persists it', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ access_token: 'jwt-1', staff_id: 's-1', expires_in: 3600 }),
    })));
    const before = Date.now();
    await login({ pin: '1234' });
    const state = staffStore.getState();
    expect(state.token).toBe('jwt-1');
    expect(state.expiresAt).not.toBeNull();
    // AC-1 allows a +/-5 s clock tolerance around Date.now() + expires_in * 1000
    expect(state.expiresAt! - before).toBeGreaterThanOrEqual(3_600_000 - 5_000);
    expect(state.expiresAt! - before).toBeLessThanOrEqual(3_600_000 + 5_000);
    const stored = JSON.parse(localStorage.getItem('staff-storage') || '{}');
    expect(stored.state.expiresAt).toBe(state.expiresAt);
  });

  it('logout() and destroySession() null expiresAt together with the token', () => {
    staffStore.getState().setSession('sweep-me', true);
    staffStore.getState().setExpiresAt(1_700_003_600_000);
    staffStore.getState().logout();
    expect(staffStore.getState().token).toBeNull();
    expect(staffStore.getState().expiresAt).toBeNull();
    staffStore.getState().setSession('sweep-me-2', false);
    staffStore.getState().setExpiresAt(1_700_003_600_000);
    destroySession();
    expect(staffStore.getState().token).toBeNull();
    expect(staffStore.getState().expiresAt).toBeNull();
    expect(localStorage.getItem('staff-storage')).toBeNull();
    expect(sessionStorage.getItem('staff-storage')).toBeNull();
  });

  it('treats a rehydrated but already-expired token as logged out (hydrated guard)', async () => {
    // Envelope from a 12h-old shift: token present, expiry in the past.
    localStorage.setItem('staff-storage', JSON.stringify({
      state: { token: 'stale-shift-token', expiresAt: 1_600_000_000_000, soundEnabled: true },
    }));
    await staffStore.persist.rehydrate();
    expect(staffStore.getState().token).toBeNull();
    expect(staffStore.getState().expiresAt).toBeNull();
    // destroySession semantics: all four slots empty.
    expect(localStorage.getItem('staff-storage')).toBeNull();
    expect(sessionStorage.getItem('staff-storage')).toBeNull();
    expect(localStorage.getItem('tq_staff_token')).toBeNull();
    expect(sessionStorage.getItem('tq_staff_token')).toBeNull();
  });

  it('sweeps the session when expiresAt passes while the tab is open (expiry timer)', () => {
    vi.useFakeTimers();
    vi.setSystemTime(1_700_000_000_000);
    staffStore.getState().setSession('live-token', true);
    staffStore.getState().setExpiresAt(1_700_000_030_000); // +30 s
    expect(staffStore.getState().token).toBe('live-token');
    // Not yet expired: untouched.
    vi.advanceTimersByTime(29_000);
    expect(staffStore.getState().token).toBe('live-token');
    expect(localStorage.getItem('staff-storage')).not.toBeNull();
    // Past the deadline: the watcher runs the full sweep, no network call.
    vi.advanceTimersByTime(2_000);
    expect(staffStore.getState().token).toBeNull();
    expect(staffStore.getState().expiresAt).toBeNull();
    expect(localStorage.getItem('staff-storage')).toBeNull();
    expect(sessionStorage.getItem('staff-storage')).toBeNull();
  });

  it('isSessionExpired: null expiry is unknown, not expired; future expiry is live', () => {
    expect(isSessionExpired({ token: null, expiresAt: 1 })).toBe(false);
    expect(isSessionExpired({ token: 't', expiresAt: null })).toBe(false);
    expect(isSessionExpired({ token: 't', expiresAt: Date.now() + 60_000 })).toBe(false);
    expect(isSessionExpired({ token: 't', expiresAt: Date.now() - 1 })).toBe(true);
    expect(isSessionExpired({ token: 't', expiresAt: Date.now() })).toBe(true);
  });
});

describe('T30 session contract', () => {
  it('setSession(token, true) writes the envelope to localStorage only', () => {
    staffStore.getState().setSession('remembered-token', true);
    const stored = JSON.parse(localStorage.getItem('staff-storage') ?? 'null');
    expect(stored?.state?.token).toBe('remembered-token');
    expect(sessionStorage.getItem('staff-storage')).toBeNull();
  });

  it('setSession(token, false) writes the envelope to sessionStorage only', () => {
    staffStore.getState().setSession('session-token', false);
    const stored = JSON.parse(sessionStorage.getItem('staff-storage') ?? 'null');
    expect(stored?.state?.token).toBe('session-token');
    expect(localStorage.getItem('staff-storage')).toBeNull();
  });

  it('destroySession clears all four slots and the in-memory token', () => {
    staffStore.getState().setSession('token-1', true);
    staffStore.getState().setSession('token-2', false);
    // Simulate leftover legacy bare-JWT slots from the pre-T30 dual write.
    localStorage.setItem('tq_staff_token', 'legacy-token');
    sessionStorage.setItem('tq_staff_token', 'legacy-token');
    destroySession();
    expect(staffStore.getState().token).toBeNull();
    expect(localStorage.getItem('staff-storage')).toBeNull();
    expect(sessionStorage.getItem('staff-storage')).toBeNull();
    expect(localStorage.getItem('tq_staff_token')).toBeNull();
    expect(sessionStorage.getItem('tq_staff_token')).toBeNull();
  });
});
