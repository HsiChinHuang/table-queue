import { get, patch } from './client';

export interface Settings {
  branch_id: string;
  waitlist_enabled: boolean;
  call_timeout_minutes: number;
  queue_prefix: string;
  // optional fields per R-F14-4
  restaurant_name?: string;
  address?: string;
  phone?: string;
  open_time?: string;
  close_time?: string;
  avg_seat_minutes?: number;
  sound_enabled_default?: boolean;
}

export interface UpdateSettingsRequest {
  waitlist_enabled?: boolean;
  call_timeout_minutes?: number;
  queue_prefix?: string;
  // optional fields per R-F14-4
  restaurant_name?: string;
  address?: string;
  phone?: string;
  open_time?: string;
  close_time?: string;
  avg_seat_minutes?: number;
  sound_enabled_default?: boolean;
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
