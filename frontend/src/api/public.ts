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

// JoinResult includes status_token and status_url from backend 201 response
export interface JoinResult extends WaitlistEntry {
  status_token: string;
  status_url: string;
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

// Factor type for ownership verification - either token or phone_last3
export type OwnershipFactor = { token: string } | { phone_last3: string };

// AC-6: getPublicBranch endpoint
export async function getPublicBranch(branchId: string): Promise<PublicBranch> {
  const result = await get<PublicBranch>(`/public/branches/${branchId}`);
  return result!;
}

// AC-6: getBoard endpoint
export async function getBoard(branchId: number): Promise<BoardResponse> {
  const result = await get<BoardResponse>(`/public/branches/${branchId}/board`);
  return result!;
}

// AC-6: joinWaitlist endpoint
export async function joinWaitlist(branchId: number, request: JoinWaitlistRequest): Promise<WaitlistEntry> {
  const result = await post<WaitlistEntry>(`/branches/${branchId}/waitlist`, request);
  return result!;
}

// AC-6: getStatus endpoint with ownership factor
export async function getStatus(queueNumber: string, factor: OwnershipFactor): Promise<WaitlistEntry | null> {
  const params: Record<string, string> = 'token' in factor 
    ? { token: factor.token }
    : { phone_last3: factor.phone_last3 };
  return get<WaitlistEntry>(`/waitlist/${queueNumber}`, undefined, params);
}

// AC-6: cancelWaitlist endpoint with ownership factor
export async function cancelWaitlist(queueNumber: string, factor: OwnershipFactor): Promise<{ success: boolean }> {
  const body: Record<string, string> = 'token' in factor 
    ? { token: factor.token }
    : { phone_last3: factor.phone_last3 };
  const result = await post<{ success: boolean }>(`/waitlist/${queueNumber}/cancel`, body);
  return result!;
}
