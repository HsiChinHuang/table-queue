export const ERROR_MESSAGES: Record<string, string> = {
  VALIDATION_ERROR: 'Validation error. Please check your input.',
  WAITLIST_DUPLICATE_PHONE: 'This phone number is already on the waitlist.',
  WAITLIST_NOT_FOUND: 'Waitlist entry not found.',
  WAITLIST_INVALID_STATUS: 'Invalid status for this action.',
  WAITLIST_CLOSED: 'Waitlist is currently closed.',
  AUTH_INVALID_PIN: 'Invalid PIN. Please try again.',
  AUTH_TOKEN_EXPIRED: 'Session expired. Please login again.',
  TABLE_NOT_FOUND: 'Table not found.',
  TABLE_NOT_AVAILABLE: 'Table is not available.',
  CONFLICT: 'Conflict with another change. Please try again.',
  RATE_LIMITED: 'Too many requests. Please try again.',
  INTERNAL_ERROR: 'Something went wrong. Please try again.',
  BRANCH_NOT_FOUND: 'Branch not found.',
  NETWORK_ERROR: 'Network error. Please check your connection.',
};

export class ApiError extends Error {
  code: string;
  statusCode: number;
  details?: Record<string, unknown>;

  constructor(code: string, statusCode: number, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
  }
}

export function getErrorMessage(code: string): string {
  return ERROR_MESSAGES[code] || 'An unexpected error occurred.';
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}
