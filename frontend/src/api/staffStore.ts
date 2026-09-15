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
 * KNOWN DEFERRED (T30, by operator directive): LoginPage still keeps a raw
 * `tq_staff_token` copy for remember-me and logout does not sweep every slot.
 * That durable-copy hygiene fix stays scoped to T30 - this file only removes the
 * second STORE so the app has one session truth.
 */
import { staffStore } from '@/stores/staffStore';

export type { StaffStore } from '@/stores/staffStore';

/** The one and only session hook - same store instance as `@/stores/staffStore`. */
export const useStaffStore = staffStore;

/** Object-style facade for non-component callers (client.ts). */
export const staffStoreCompat = {
  get token(): string | null {
    return staffStore.getState().token;
  },
  setToken: (token: string | null) => staffStore.getState().setToken(token),
  clearToken: () => staffStore.getState().logout(),
};

export { staffStoreCompat as staffStore };

export default useStaffStore;
