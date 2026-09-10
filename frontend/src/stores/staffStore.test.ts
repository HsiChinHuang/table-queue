import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { staffStore } from './staffStore';

describe('staffStore', () => {
  beforeEach(() => {
    staffStore.setState({ token: null, soundEnabled: true });
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
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
