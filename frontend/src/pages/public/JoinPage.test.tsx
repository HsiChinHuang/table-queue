// @vitest-environment jsdom

import { describe, it, expect } from 'vitest';
import { validateJoinForm } from './JoinPage';

describe('validateJoinForm', () => {
  describe('Name validation', () => {
    it('should be invalid with empty string', () => {
      const result = validateJoinForm({
        name: '',
        phone: '0921-234-567',
        partySize: 2,
      });
      expect(result.isValid).toBe(false);
      expect(result.errors.name).toBe('Name is required');
    });

    it('should be invalid with 51 characters', () => {
      const longName = 'a'.repeat(51);
      const result = validateJoinForm({
        name: longName,
        phone: '0921-234-567',
        partySize: 2,
      });
      expect(result.isValid).toBe(false);
      expect(result.errors.name).toBe('Name must be 50 characters or less');
    });

    it('should be valid with 1 character', () => {
      const result = validateJoinForm({
        name: 'a',
        phone: '0921-234-567',
        partySize: 2,
      });
      expect(result.isValid).toBe(true);
      expect(result.errors.name).toBeUndefined();
    });

    it('should be valid with 50 characters', () => {
      const exactName = 'a'.repeat(50);
      const result = validateJoinForm({
        name: exactName,
        phone: '0921-234-567',
        partySize: 2,
      });
      expect(result.isValid).toBe(true);
      expect(result.errors.name).toBeUndefined();
    });
  });

  describe('Phone validation', () => {
    it('should be valid with mobile 0921234567', () => {
      const result = validateJoinForm({
        name: 'John',
        phone: '0921234567',
        partySize: 2,
      });
      expect(result.isValid).toBe(true);
      expect(result.errors.phone).toBeUndefined();
    });

    it('should be valid with mobile 0921-234-567', () => {
      const result = validateJoinForm({
        name: 'John',
        phone: '0921-234-567',
        partySize: 2,
      });
      expect(result.isValid).toBe(true);
      expect(result.errors.phone).toBeUndefined();
    });

    it('should be valid with landline 0223456789', () => {
      const result = validateJoinForm({
        name: 'John',
        phone: '0223456789',
        partySize: 2,
      });
      expect(result.isValid).toBe(true);
      expect(result.errors.phone).toBeUndefined();
    });

    it('should be valid with landline 02-2345-6789', () => {
      const result = validateJoinForm({
        name: 'John',
        phone: '02-2345-6789',
        partySize: 2,
      });
      expect(result.isValid).toBe(true);
      expect(result.errors.phone).toBeUndefined();
    });

    it('should be invalid with 1234', () => {
      const result = validateJoinForm({
        name: 'John',
        phone: '1234',
        partySize: 2,
      });
      expect(result.isValid).toBe(false);
      expect(result.errors.phone).toBeDefined();
    });

    it('should be invalid with 0800123456 (08xx is not valid)', () => {
      const result = validateJoinForm({
        name: 'John',
        phone: '0800123456',
        partySize: 2,
      });
      expect(result.isValid).toBe(false);
      expect(result.errors.phone).toBeDefined();
    });
  });

  describe('Party size validation', () => {
    it('should be invalid with 0', () => {
      const result = validateJoinForm({
        name: 'John',
        phone: '0921-234-567',
        partySize: 0,
      });
      expect(result.isValid).toBe(false);
      expect(result.errors.partySize).toBe('Party size must be at least 1');
    });

    it('should be invalid with 21', () => {
      const result = validateJoinForm({
        name: 'John',
        phone: '0921-234-567',
        partySize: 21,
      });
      expect(result.isValid).toBe(false);
      expect(result.errors.partySize).toBe('Party size must be 20 or less');
    });

    it('should be valid with 1', () => {
      const result = validateJoinForm({
        name: 'John',
        phone: '0921-234-567',
        partySize: 1,
      });
      expect(result.isValid).toBe(true);
      expect(result.errors.partySize).toBeUndefined();
    });

    it('should be valid with 20', () => {
      const result = validateJoinForm({
        name: 'John',
        phone: '0921-234-567',
        partySize: 20,
      });
      expect(result.isValid).toBe(true);
      expect(result.errors.partySize).toBeUndefined();
    });
  });

  describe('Note validation', () => {
    it('should be invalid with 201 characters', () => {
      const longNote = 'a'.repeat(201);
      const result = validateJoinForm({
        name: 'John',
        phone: '0921-234-567',
        partySize: 2,
        note: longNote,
      });
      expect(result.isValid).toBe(false);
      expect(result.errors.note).toBe('Note must be 200 characters or less');
    });

    it('should be valid with 200 characters', () => {
      const exactNote = 'a'.repeat(200);
      const result = validateJoinForm({
        name: 'John',
        phone: '0921-234-567',
        partySize: 2,
        note: exactNote,
      });
      expect(result.isValid).toBe(true);
      expect(result.errors.note).toBeUndefined();
    });

    it('should be valid with empty string', () => {
      const result = validateJoinForm({
        name: 'John',
        phone: '0921-234-567',
        partySize: 2,
        note: '',
      });
      expect(result.isValid).toBe(true);
      expect(result.errors.note).toBeUndefined();
    });
  });
});
