// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { tokenStorageFor } from './LoginPage';

describe('tokenStorageFor', () => {
  it('returns localStorage when remember is true', () => {
    expect(tokenStorageFor(true)).toBe('localStorage');
  });

  it('returns sessionStorage when remember is false', () => {
    expect(tokenStorageFor(false)).toBe('sessionStorage');
  });
});
