import { create } from 'zustand';
import { persist, type PersistStorage, type StorageValue } from 'zustand/middleware';

/**
 * The ONE staff session store (T30).
 *
 * T30 (SEC AUDIT HIGH C-1/C-2/C-3): the staff JWT now lives in exactly one of the
 * four storage slots - this store's own persist envelope (`staff-storage`) - and
 * remember-me chooses the slot (ON = localStorage, OFF = sessionStorage with zero
 * durable copies). A single dynamic storage adapter owns every write so a login can
 * never land a second copy, and `destroySession` sweeps all four slots plus the
 * in-memory token so logout and 401 leave no live JWT behind.
 *
 * The four slots: {localStorage, sessionStorage} x {tq_staff_token, staff-storage}.
 * `tq_staff_token` is the legacy bare-JWT key (no longer written by product code);
 * it is only ever removed (startup migration + destroySession).
 */

const STORAGE_KEY = 'staff-storage';
const LEGACY_RAW_KEY = 'tq_staff_token';

/** The shape the persist middleware serialises (see `partialize` below). */
type PersistedState = { token: string | null; soundEnabled: boolean };

// remember-me preference. Module-level (not in the persisted state) because the
// storage adapter must read it synchronously on every write, including during the
// store's own rehydration where the store instance is not yet bound.
let rememberMe = true;

// T30 AC-5: startup migration. A browser upgraded from the HEAD-era dual-write build
// carries the legacy bare-JWT key in BOTH storages. Purge it the moment this module
// loads - LoginPage, client.ts and StaffLayout all import it at startup, so any entry
// point that loads the staff tree triggers the purge.
if (typeof window !== 'undefined') {
  window.localStorage.removeItem(LEGACY_RAW_KEY);
  window.sessionStorage.removeItem(LEGACY_RAW_KEY);
}

// Dynamic storage adapter: the persist envelope lands in the storage chosen by
// remember-me, and exactly one slot ever carries it (the other is swept on every
// write). A token-less envelope removes the slot instead of leaving it behind, so a
// logout/401 re-persist can never recreate a durable copy.
const dynamicStorage: PersistStorage<PersistedState> = {
  getItem: (name: string): StorageValue<PersistedState> | null => {
    if (typeof window === 'undefined') return null;
    const raw = window.localStorage.getItem(name) ?? window.sessionStorage.getItem(name);
    if (raw === null) return null;
    try {
      return JSON.parse(raw) as StorageValue<PersistedState>;
    } catch {
      return null;
    }
  },
  setItem: (name: string, value: StorageValue<PersistedState>): void => {
    if (typeof window === 'undefined') return;
    const token = value.state?.token ?? null;
    if (!token) {
      window.localStorage.removeItem(name);
      window.sessionStorage.removeItem(name);
      return;
    }
    const target = rememberMe ? window.localStorage : window.sessionStorage;
    // Sweep both storages first so exactly one slot carries the envelope.
    window.localStorage.removeItem(name);
    window.sessionStorage.removeItem(name);
    target.setItem(name, JSON.stringify(value));
  },
  removeItem: (name: string): void => {
    if (typeof window === 'undefined') return;
    window.localStorage.removeItem(name);
    window.sessionStorage.removeItem(name);
  },
};

export interface StaffStore {
  token: string | null;
  soundEnabled: boolean;
  setToken: (token: string | null) => void;
  /** T30: set the token AND the remember-me preference in one write. */
  setSession: (token: string, remember: boolean) => void;
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
      setSession: (token, remember) => {
        rememberMe = remember;
        set({ token });
      },
      logout: () => set({ token: null }),
      clearToken: () => set({ token: null }),
      setSoundEnabled: (enabled) => set({ soundEnabled: enabled }),
    }),
    {
      name: STORAGE_KEY,
      storage: dynamicStorage,
      partialize: (state): PersistedState => ({
        token: state.token,
        soundEnabled: state.soundEnabled,
      }),
    }
  )
);

/**
 * T30: a real logout. Sweeps ALL four storage slots (both storages x both keys) plus
 * the in-memory token, so a logged-out shared front-desk terminal holds no live JWT.
 * Called by the StaffLayout logout button and the client 401 handler.
 */
export function destroySession(): void {
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(LEGACY_RAW_KEY);
    window.sessionStorage.removeItem(LEGACY_RAW_KEY);
    window.localStorage.removeItem(STORAGE_KEY);
    window.sessionStorage.removeItem(STORAGE_KEY);
  }
  // Null the in-memory token. (The wrapped setState re-persists, but the token-less
  // envelope is dropped by the storage adapter, so no slot is recreated.)
  staffStore.setState({ token: null });
}
