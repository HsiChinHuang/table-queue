import { get, post, patch } from './client';

export interface WaitlistEntry {
  id: string;
  queue_number: string;
  full_queue_number: string;
  phone: string;
  party_size: number;
  status: string;
  table_id: string | null;
  created_at?: string;
}

export interface EditWaitlistRequest {
  phone?: string;
  party_size?: number;
  name?: string;
}

export interface ReorderRequest {
  entry_ids: string[];
}

// AC-6: listWaitlist endpoint
export async function listWaitlist(_branchId: string): Promise<WaitlistEntry[]> {
  const result = await get<WaitlistEntry[]>('/staff/waitlist');
  return result!;
}

// AC-6: callWaitlist endpoint
export async function callWaitlist(entryId: string): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>(`/staff/waitlist/${entryId}/call`);
  return result!;
}

// AC-6: seatWaitlist endpoint
export async function seatWaitlist(entryId: string, tableId: string): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>(`/staff/waitlist/${entryId}/seat`, { table_id: tableId });
  return result!;
}

// AC-6: noShowWaitlist endpoint
export async function noShowWaitlist(entryId: string): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>(`/staff/waitlist/${entryId}/no-show`);
  return result!;
}

// AC-6: restoreWaitlist endpoint
export async function restoreWaitlist(entryId: string): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>(`/staff/waitlist/${entryId}/restore`);
  return result!;
}

// AC-6: revertWaitlist endpoint
export async function revertWaitlist(entryId: string): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>(`/staff/waitlist/${entryId}/revert`);
  return result!;
}

// AC-6: cancelWaitlistByStaff endpoint
export async function cancelWaitlistByStaff(entryId: string): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>(`/staff/waitlist/${entryId}/cancel`);
  return result!;
}

// AC-6: editWaitlist endpoint
export async function editWaitlist(entryId: string, request: EditWaitlistRequest): Promise<WaitlistEntry> {
  const result = await patch<WaitlistEntry>(`/staff/waitlist/${entryId}`, request);
  return result!;
}

// AC-6: reorderWaitlist endpoint
export async function reorderWaitlist(request: ReorderRequest): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>('/staff/waitlist/reorder', request);
  return result!;
}
