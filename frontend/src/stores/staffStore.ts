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
type PersistedState = {
  token: string | null;
  /** T17 AC-1: epoch ms when the token expires; null when no expiry is known. */
  expiresAt: number | null;
  soundEnabled: boolean;
};

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
  /** T17 AC-1: epoch ms when the token expires; null when no expiry is known. */
  expiresAt: number | null;
  soundEnabled: boolean;
  setToken: (token: string | null) => void;
  /** T17: set the token's expiry (epoch ms) alongside the token. */
  setExpiresAt: (expiresAt: number | null) => void;
  /** T30: set the token AND the remember-me preference in one write. */
  setSession: (token: string, remember: boolean) => void;
  logout: () => void;
  /** Alias of `logout` - the name `StaffLayout`'s destructure and `client.ts` call. */
  clearToken: () => void;
  setSoundEnabled: (enabled: boolean) => void;
}

/**
 * T17 AC-1: true when a token is present, its expiry is KNOWN, and that expiry is
 * at or before now. Unknown expiry (null) is NOT treated as expired - the backend
 * always issues a bounded lifetime, but a null here must not log staff out.
 */
export function isSessionExpired(state: { token: string | null; expiresAt: number | null }): boolean {
  return state.token !== null && state.expiresAt !== null && Date.now() >= state.expiresAt;
}

export const staffStore = create<StaffStore>()(
  persist(
    (set) => ({
      token: null,
      expiresAt: null,
      soundEnabled: true,
      setToken: (token) => set({ token }),
      setExpiresAt: (expiresAt) => set({ expiresAt }),
      setSession: (token, remember) => {
        rememberMe = remember;
        set({ token });
      },
      // T17 AC-1: logout nulls the expiry together with the token.
      logout: () => set({ token: null, expiresAt: null }),
      clearToken: () => set({ token: null, expiresAt: null }),
      setSoundEnabled: (enabled) => set({ soundEnabled: enabled }),
    }),
    {
      name: STORAGE_KEY,
      storage: dynamicStorage,
      // T17 AC-1: the persisted envelope carries expiresAt so a reload rehydrates
      // the full session (token + expiry), not a bare token.
      partialize: (state): PersistedState => ({
        token: state.token,
        expiresAt: state.expiresAt,
        soundEnabled: state.soundEnabled,
      }),
      // T17 AC-1 (hydrated guard): if rehydration restores an already-expired
      // session, treat it as logged out BEFORE any staff UI renders - the full
      // destroySession sweep runs (token null + all four slots emptied).
      onRehydrateStorage: () => (state) => {
        if (state && isSessionExpired(state)) {
          destroySession();
        }
      },
    }
  )
);

// T17 AC-1 (expiry timer): while a session is live, a single watcher is armed at
// expiresAt and performs the same destroySession sweep (no network call) when the
// deadline passes. The watcher re-arms on every token/expiry change; it never arms
// for a token without a known expiry or for one that is already expired.
if (typeof window !== 'undefined') {
  let expiryTimer: ReturnType<typeof setTimeout> | null = null;
  const armExpiryWatch = (state: Pick<StaffStore, 'token' | 'expiresAt'>) => {
    if (expiryTimer) {
      clearTimeout(expiryTimer);
      expiryTimer = null;
    }
    const { token, expiresAt } = state;
    if (!token || expiresAt === null || expiresAt <= Date.now()) return;
    const delay = Math.min(expiresAt - Date.now(), 2_147_483_647); // setTimeout cap
    expiryTimer = setTimeout(() => {
      expiryTimer = null;
      const current = staffStore.getState();
      if (isSessionExpired(current)) destroySession();
    }, delay);
  };
  staffStore.subscribe((state, prev) => {
    if (state.token !== prev.token || state.expiresAt !== prev.expiresAt) {
      armExpiryWatch(state);
    }
  });
}

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
  // Null the in-memory token AND its expiry. (The wrapped setState re-persists, but
  // the token-less envelope is dropped by the storage adapter, so no slot is
  // recreated.) T17 AC-1: the expiry dies with the token.
  staffStore.setState({ token: null, expiresAt: null });
}
