/**
 * Compatibility surface over the ONE staff session store (`@/stores/staffStore`).
 *
 * This module used to be a SECOND zustand store with its own persist key
 * (`tq_staff_token`). Two persisted stores disagreeing about the session token is
 * exactly the audit finding T30 records (C-1/C-2/C-3): LoginPage wrote to
 * `@/stores/staffStore` (key `staff-storage`) while StaffLayout's auth guard read
 * this one - so a correct PIN login could never satisfy the guard and the staff
 * area bounced every navigation back to the login screen.
 *
 * The session state now lives in exactly one zustand store. What remains here is
 * the shape older modules import: the `useStaffStore` hook and the
 * `staffStore.token / setToken / clearToken` facade used by `client.ts`.
 *
 * T30 (resolved): the raw `tq_staff_token` dual write is gone and logout/401 now
 * call `destroySession`, which sweeps all four storage slots plus the in-memory
 * token. This file only re-exports that contract; it defines no store of its own.
 */
import { staffStore } from '@/stores/staffStore';

export type { StaffStore } from '@/stores/staffStore';
export { destroySession } from '@/stores/staffStore';

/** The one and only session hook - same store instance as `@/stores/staffStore`. */
export const useStaffStore = staffStore;

/** Object-style facade for non-component callers (client.ts). */
export const staffStoreCompat = {
  get token(): string | null {
    return staffStore.getState().token;
  },
  /** T17: the token's known expiry (epoch ms) - null when unknown. */
  get expiresAt(): number | null {
    return staffStore.getState().expiresAt;
  },
  setToken: (token: string | null) => staffStore.getState().setToken(token),
  /** T17: record the token's expiry alongside the token. */
  setExpiresAt: (expiresAt: number | null) => staffStore.getState().setExpiresAt(expiresAt),
  clearToken: () => staffStore.getState().logout(),
};

export { staffStoreCompat as staffStore };

export default useStaffStore;
