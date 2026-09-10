/**
 * Zustand store for staff-side UI state.
 * Moved from stores/ to api/ per F-03.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface StaffStore {
  token: string | null;
  soundEnabled: boolean;
  setToken: (token: string | null) => void;
  toggleSound: () => void;
  clearAuth: () => void;
}

export const staffStore = create<StaffStore>()(
  persist(
    (set) => ({
      token: null,
      soundEnabled: true,
      setToken: (token) => set({ token }),
      toggleSound: () =>
        set((state) => ({ soundEnabled: !state.soundEnabled })),
      clearAuth: () => set({ token: null, soundEnabled: true }),
    }),
    {
      name: 'staff-store',
      partialize: (state) => ({
        token: state.token,
        soundEnabled: state.soundEnabled,
      }),
    }
  )
);
