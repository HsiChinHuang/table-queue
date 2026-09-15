import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface StaffStore {
  token: string | null;
  soundEnabled: boolean;
  setToken: (token: string | null) => void;
  logout: () => void;
  /** Alias of `logout` - the name `StaffLayout`'s destructure and `client.ts` call. */
  clearToken: () => void;
  setSoundEnabled: (enabled: boolean) => void;
}

export const staffStore = create<StaffStore>()(
  persist(
    (set) => ({
      token: null,
      soundEnabled: true,
      setToken: (token) => set({ token }),
      logout: () => set({ token: null }),
      clearToken: () => set({ token: null }),
      setSoundEnabled: (enabled) => set({ soundEnabled: enabled }),
    }),
    {
      name: 'staff-storage',
      partialize: (state) => ({
        token: state.token,
        soundEnabled: state.soundEnabled,
      }),
    }
  )
);
