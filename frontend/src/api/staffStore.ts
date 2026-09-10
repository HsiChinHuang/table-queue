import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface StaffStoreState {
  token: string | null;
  staffId: string | null;
}

interface StaffStoreActions {
  setToken: (token: string | null) => void;
  clearToken: () => void;
}

export type StaffStore = StaffStoreState & StaffStoreActions;

export const useStaffStore = create<StaffStore>()(
  persist(
    (set) => ({
      token: null,
      staffId: null,
      setToken: (token) => set({ token, staffId: token ? `staff-${token.slice(-4)}` : null }),
      clearToken: () => set({ token: null, staffId: null }),
    }),
    { name: 'tq_staff_token' }
  )
);

// Export for backward compatibility
export const staffStore = {
  get token() { return useStaffStore.getState().token; },
  setToken: (token: string | null) => useStaffStore.getState().setToken(token),
  clearToken: () => useStaffStore.getState().clearToken(),
};

export default useStaffStore;
