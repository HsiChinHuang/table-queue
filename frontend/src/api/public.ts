import { get, post } from './client';

export interface PublicBranch {
  id: string;
  name: string;
  restaurant_id: string;
  timezone: string;
  cutoff_hour: number;
  restaurant_name: string;
  branch_name: string;
  hours: string;
  waiting_count: number;
  is_waitlist_open: boolean;
}

export interface JoinWaitlistRequest {
  phone: string;
  party_size: number;
  name?: string;
}

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

export interface BoardResponse {
  branch_id: string;
  current_call: WaitlistEntry | null;
  next_up: WaitlistEntry | null;
  recent_calls: WaitlistEntry[];
  waiting_count: number;
}

// AC-6: getPublicBranch endpoint
export async function getPublicBranch(branchId: string): Promise<PublicBranch> {
  const result = await get<PublicBranch>(`/public/branches/${branchId}`);
  return result!;
}

// AC-6: getBoard endpoint
export async function getBoard(branchId: string): Promise<BoardResponse> {
  const result = await get<BoardResponse>(`/public/board/${branchId}`);
  return result!;
}

// AC-6: joinWaitlist endpoint
export async function joinWaitlist(request: JoinWaitlistRequest): Promise<WaitlistEntry> {
  const result = await post<WaitlistEntry>('/public/waitlist', request);
  return result!;
}

// AC-6: getStatus endpoint
export async function getStatus(queueNumber: string): Promise<WaitlistEntry | null> {
  return get<WaitlistEntry>(`/public/waitlist/${queueNumber}`);
}

// AC-6: cancelWaitlist endpoint
export async function cancelWaitlist(queueNumber: string): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>(`/public/waitlist/${queueNumber}/cancel`);
  return result!;
}
