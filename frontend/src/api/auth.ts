import { post } from './client';
import { staffStore } from './staffStore';

export interface LoginRequest {
  pin: string;
}

export interface LoginResponse {
  token: string;
  staff_id: string;
  expires_at: string;
}

export interface ChangePinRequest {
  old_pin: string;
  new_pin: string;
}

// AC-6: login endpoint
export async function login(request: LoginRequest): Promise<LoginResponse> {
  const response = await post<LoginResponse>('/staff/login', request);
  if (response?.token) {
    staffStore.setToken(response.token);
  }
  return response!;
}

// AC-6: changePin endpoint
export async function changePin(request: ChangePinRequest): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>('/staff/pin/change', request);
  return result!;
}
