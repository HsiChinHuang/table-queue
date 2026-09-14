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
  }
  return response!;
}

// AC-6: changePin endpoint
export async function changePin(request: ChangePinRequest): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>('/auth/change-pin', request);
  return result!;
}
