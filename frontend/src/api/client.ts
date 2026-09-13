import { staffStore } from './staffStore';
import { ApiError, getErrorMessage } from './errors';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const TIMEOUT_MS = 30000;

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

async function mockRequest(method: string, path: string, body?: unknown): Promise<unknown> {
  // Mock implementation - will be detailed in mock/index.ts
  const { mockHandlers } = await import('./mock');
  const handler = mockHandlers.get(`${method}:${path}`);
  if (handler) {
    return handler(body);
  }
  // Default mock response
  return { success: true, data: null };
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T | null> {
  const { method = 'GET', body, headers: customHeaders = {} } = options;

  // AC-8: Check for mock mode.
  // I-01 mock-request-handler marker: with VITE_USE_MOCK=false this whole branch is
  // dead code, rollup eliminates it and the mock chunk is never linked, so a built
  // asset that contains 'mock-request-handler' means the mock layer is still reachable.
  if (import.meta.env.VITE_USE_MOCK === 'true') {
    return mockRequest(method, path, body) as T | null; // mock-request-handler
  }

  const url = `${API_BASE_URL}${path}`;
  const token = staffStore.token;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...customHeaders,
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  // AC-3: AbortController for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    // AC-3: Handle 204 No Content
    if (response.status === 204) {
      return null;
    }

    const data = await response.json();

    // AC-3: Handle 401 - clear token, redirect to login
    if (response.status === 401) {
      staffStore.clearToken();
      // Clear query cache would be handled by calling code
      window.location.href = '/staff/login';
      throw new ApiError('AUTH_TOKEN_EXPIRED', 401, 'Session expired. Please login again.');
    }

    // AC-3: Handle 429 - Too many requests
    if (response.status === 429) {
      // Toast handled by calling code or global error handler
      throw new ApiError('RATE_LIMITED', 429, 'Too many requests. Please try again.');
    }

    // Handle success
    if (response.ok) {
      return data as T;
    }

    // AC-3: 5xx -> generic toast message (Implementation notes item 7)
    if (response.status >= 500) {
      throw new ApiError('INTERNAL_ERROR', response.status, 'Something went wrong. Please try again.');
    }

    // Handle other error codes
    const error = data.error || data;
    const code = error.code || 'INTERNAL_ERROR';
    const message = error.message || getErrorMessage(code);
    throw new ApiError(code, response.status, message, error.details);
  } catch (error) {
    clearTimeout(timeoutId);

    // AC-3: Handle network errors
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiError('NETWORK_ERROR', 0, 'Request timed out. Please check your connection.');
    }

    // Re-throw ApiError or create NETWORK_ERROR
    if (error instanceof ApiError) {
      throw error;
    }

    // AC-3: Network error fallback
    throw new ApiError('NETWORK_ERROR', 0, 'Network error. Please check your connection.');
  }
}

// HTTP method wrappers
export async function get<T>(path: string, headers?: Record<string, string>): Promise<T | null> {
  return request<T>(path, { method: 'GET', headers });
}

export async function post<T>(path: string, body?: unknown, headers?: Record<string, string>): Promise<T | null> {
  return request<T>(path, { method: 'POST', body, headers });
}

export async function put<T>(path: string, body?: unknown, headers?: Record<string, string>): Promise<T | null> {
  return request<T>(path, { method: 'PUT', body, headers });
}

export async function patch<T>(path: string, body?: unknown, headers?: Record<string, string>): Promise<T | null> {
  return request<T>(path, { method: 'PATCH', body, headers });
}

export async function del<T>(path: string, headers?: Record<string, string>): Promise<T | null> {
  return request<T>(path, { method: 'DELETE', headers });
}

export { API_BASE_URL };
