import { get, patch } from './client';

export interface Settings {
  branch_id: string;
  waitlist_enabled: boolean;
  call_timeout_minutes: number;
  queue_prefix: string;
}

export interface UpdateSettingsRequest {
  waitlist_enabled?: boolean;
  call_timeout_minutes?: number;
  queue_prefix?: string;
}

// AC-6: getSettings endpoint
export async function getSettings(_branchId: string): Promise<Settings> {
  const result = await get<Settings>('/staff/settings');
  return result!;
}

// AC-6: updateSettings endpoint
export async function updateSettings(request: UpdateSettingsRequest): Promise<{ success: boolean }> {
  const result = await patch<{ success: boolean }>('/staff/settings', request);
  return result!;
}
