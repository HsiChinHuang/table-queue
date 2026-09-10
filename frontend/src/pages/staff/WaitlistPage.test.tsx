// @vitest-environment jsdom

import { describe, it, expect } from 'vitest';
import { filterByStatus, WaitlistEntry } from './WaitlistPage';

describe('filterByStatus', () => {
  const mockEntries: WaitlistEntry[] = [
    {
      id: '1',
      queue_number: 'A001',
      full_queue_number: 'A-20260910-001',
      phone: '0912-345-678',
      party_size: 4,
      status: 'WAITING',
      table_id: null,
      name: 'John Doe',
      sort_order: 1,
    },
    {
      id: '2',
      queue_number: 'A002',
      full_queue_number: 'A-20260910-002',
      phone: '0923-456-789',
      party_size: 2,
      status: 'CALLED',
      table_id: null,
      name: 'Jane Smith',
      sort_order: 2,
    },
    {
      id: '3',
      queue_number: 'A003',
      full_queue_number: 'A-20260910-003',
      phone: '0934-567-890',
      party_size: 6,
      status: 'SEATED',
      table_id: 'table-1',
      name: 'Bob Johnson',
      sort_order: 3,
    },
    {
      id: '4',
      queue_number: 'A004',
      full_queue_number: 'A-20260910-004',
      phone: '0945-678-901',
      party_size: 3,
      status: 'NO_SHOW',
      table_id: null,
      name: 'Alice Brown',
      sort_order: 4,
    },
    {
      id: '5',
      queue_number: 'A005',
      full_queue_number: 'A-20260910-005',
      phone: '0956-789-012',
      party_size: 5,
      status: 'CANCELLED',
      table_id: null,
      name: 'Charlie Wilson',
      sort_order: 5,
    },
    {
      id: '6',
      queue_number: 'A006',
      full_queue_number: 'A-20260910-006',
      phone: '0967-890-123',
      party_size: 2,
      status: 'DONE',
      table_id: null,
      name: 'Diana Lee',
      sort_order: 6,
    },
  ];

  it('should return empty arrays when input is empty', () => {
    const result = filterByStatus([], 'All');
    expect(result.active).toEqual([]);
    expect(result.closed).toEqual([]);
  });

  it('should return all active statuses when filter is Active', () => {
    const result = filterByStatus(mockEntries, 'Active');
    expect(result.active.length).toBe(3);
    expect(result.active.map((e) => e.status)).toEqual(['WAITING', 'CALLED', 'SEATED']);
    expect(result.closed.length).toBe(0);
    expect(result.closed).toEqual([]);
  });

  it('should return all closed statuses when filter is Closed', () => {
    const result = filterByStatus(mockEntries, 'Closed');
    expect(result.closed.length).toBe(3);
    expect(result.closed.map((e) => e.status)).toEqual(['NO_SHOW', 'CANCELLED', 'DONE']);
    expect(result.active.length).toBe(0);
    expect(result.active).toEqual([]);
  });

  it('should return all entries when filter is All', () => {
    const result = filterByStatus(mockEntries, 'All');
    expect(result.active.length).toBe(3);
    expect(result.closed.length).toBe(3);
    expect(result.active.map((e) => e.status)).toEqual(['WAITING', 'CALLED', 'SEATED']);
    expect(result.closed.map((e) => e.status)).toEqual(['NO_SHOW', 'CANCELLED', 'DONE']);
  });
});
