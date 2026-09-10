/**
 * Tests for the API error helpers (F-15). Pure functions, node environment is enough.
 */
import { describe, expect, it } from 'vitest';
import { ApiError, ERROR_MESSAGES, getErrorMessage, isApiError } from './errors';

describe('ApiError', () => {
  it('carries code, statusCode and optional details', () => {
    const err = new ApiError('VALIDATION_ERROR', 422, 'name too long', { field: 'name' });
    expect(err.code).toBe('VALIDATION_ERROR');
    expect(err.statusCode).toBe(422);
    expect(err.details).toEqual({ field: 'name' });
    expect(err.message).toBe('name too long');
    expect(err.name).toBe('ApiError');
  });

  it('is both an Error and an ApiError', () => {
    const err = new ApiError('CONFLICT', 409, 'conflict');
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.details).toBeUndefined();
  });

  it('can be caught as an Error and narrowed with isApiError', () => {
    try {
      throw new ApiError('RATE_LIMITED', 429, 'slow down');
    } catch (error) {
      expect(error).toBeInstanceOf(Error);
      if (isApiError(error)) {
        expect(error.code).toBe('RATE_LIMITED');
        expect(error.statusCode).toBe(429);
      } else {
        expect.unreachable('isApiError should have narrowed the thrown ApiError');
      }
    }
  });
});

describe('ERROR_MESSAGES', () => {
  it('covers the documented error codes', () => {
    for (const code of [
      'VALIDATION_ERROR',
      'WAITLIST_DUPLICATE_PHONE',
      'WAITLIST_NOT_FOUND',
      'WAITLIST_INVALID_STATUS',
      'AUTH_INVALID_PIN',
      'AUTH_TOKEN_EXPIRED',
      'TABLE_NOT_FOUND',
      'RATE_LIMITED',
      'INTERNAL_ERROR',
      'BRANCH_NOT_FOUND',
      'NETWORK_ERROR',
    ]) {
      expect(ERROR_MESSAGES[code]).toBeTypeOf('string');
      expect((ERROR_MESSAGES[code] as string).length).toBeGreaterThan(0);
    }
  });

  it('uses the ui.md wording for the two most common guest-facing codes', () => {
    expect(ERROR_MESSAGES.WAITLIST_DUPLICATE_PHONE).toContain('already on the waitlist');
    expect(ERROR_MESSAGES.AUTH_INVALID_PIN).toContain('Invalid PIN');
  });
});

describe('getErrorMessage', () => {
  it('returns the mapped message for every known code', () => {
    for (const code of Object.keys(ERROR_MESSAGES)) {
      expect(getErrorMessage(code)).toBe(ERROR_MESSAGES[code]);
    }
  });

  it('falls back to a generic message for unknown codes', () => {
    expect(getErrorMessage('NOT_A_REAL_CODE')).toBe('An unexpected error occurred.');
    expect(getErrorMessage('')).toBe('An unexpected error occurred.');
  });
});

describe('isApiError', () => {
  it('accepts only ApiError instances', () => {
    expect(isApiError(new ApiError('CONFLICT', 409, 'x'))).toBe(true);
    expect(isApiError(new Error('plain'))).toBe(false);
    expect(isApiError({ code: 'CONFLICT', statusCode: 409, message: 'duck' })).toBe(false);
    expect(isApiError('CONFLICT')).toBe(false);
    expect(isApiError(null)).toBe(false);
    expect(isApiError(undefined)).toBe(false);
    expect(isApiError({})).toBe(false);
  });
});
