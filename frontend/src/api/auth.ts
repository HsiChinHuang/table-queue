import { post } from './client';
import { staffStore } from './staffStore';

export interface LoginRequest {
  pin: string;
}

export interface LoginResponse {
  access_token: string;
  staff_id: string;
  expires_in: number;
}

export interface ChangePinRequest {
  old_pin: string;
  new_pin: string;
}

// AC-6: login endpoint
export async function login(request: LoginRequest): Promise<LoginResponse> {
  const response = await post<LoginResponse>('/auth/login', request);
  if (response?.access_token) {
    staffStore.setToken(response.access_token);
    // T17 AC-1: the login response's expires_in (seconds) becomes the store's
    // expiresAt (epoch ms), so no code path can store a login token without an
    // expiry. A missing/non-positive expires_in leaves the expiry unknown (null)
    // rather than fabricating one.
    if (typeof response.expires_in === 'number' && Number.isFinite(response.expires_in) && response.expires_in > 0) {
      staffStore.setExpiresAt(Date.now() + response.expires_in * 1000);
    }
  }
  return response!;
}

// AC-6: changePin endpoint
export async function changePin(request: ChangePinRequest): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>('/auth/change-pin', request);
  return result!;
}
