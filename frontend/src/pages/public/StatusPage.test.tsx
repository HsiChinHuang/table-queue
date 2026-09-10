import { describe, expect, test } from 'vitest';
import { formatCountdown } from './StatusPage';

describe('formatCountdown', () => {
  test('0 seconds -> 00:00', () => {
    expect(formatCountdown(0)).toBe('00:00');
  });
  test('59 seconds -> 00:59', () => {
    expect(formatCountdown(59)).toBe('00:59');
  });
  test('65 seconds -> 01:05', () => {
    expect(formatCountdown(65)).toBe('01:05');
  });
  test('600 seconds -> 10:00', () => {
    expect(formatCountdown(600)).toBe('10:00');
  });
  test('3599 seconds -> 59:59', () => {
    expect(formatCountdown(3599)).toBe('59:59');
  });
});
