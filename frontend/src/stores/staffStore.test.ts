// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { staffStore, destroySession } from './staffStore';

describe('staffStore', () => {
  beforeEach(() => {
    staffStore.setState({ token: null, soundEnabled: true });
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('has initial state', () => {
    const state = staffStore.getState();
    expect(state.token).toBe(null);
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
