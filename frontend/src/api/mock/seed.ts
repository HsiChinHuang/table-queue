// Seed data for mock layer - matches specs.md section 19
// Restaurant: Sunny Bistro, Branch: Taipei Xinyi
// Tables: A1-A4 (2 pax), B1-B4 (4 pax), C1-C2 (6 pax)

export interface SeedData {
  restaurant: {
    id: string;
    name: string;
    pin: string;
  };
  branch: {
    id: string;
    name: string;
    timezone: string;
    cutoff_hour: number;
  };
  tables: Array<{
    id: string;
    name: string;
    capacity: number;
    status: string;
  }>;
  waitlist: Array<{
    id: string;
    queue_number: string;
    full_queue_number: string;
    phone: string;
    party_size: number;
    status: string;
    table_id: string | null;
  }>;
}

export const seedData: SeedData = {
  restaurant: {
    id: 'rest-001',
    name: 'Sunny Bistro',
    pin: '1234',
  },
  branch: {
    id: 'branch-001',
    name: 'Taipei Xinyi',
    timezone: 'Asia/Taipei',
    cutoff_hour: 4,
  },
  tables: [
    { id: 'table-a1', name: 'A1', capacity: 2, status: 'AVAILABLE' },
    { id: 'table-a2', name: 'A2', capacity: 2, status: 'AVAILABLE' },
    { id: 'table-a3', name: 'A3', capacity: 2, status: 'AVAILABLE' },
    { id: 'table-a4', name: 'A4', capacity: 2, status: 'AVAILABLE' },
    { id: 'table-b1', name: 'B1', capacity: 4, status: 'OCCUPIED' },
    { id: 'table-b2', name: 'B2', capacity: 4, status: 'AVAILABLE' },
    { id: 'table-b3', name: 'B3', capacity: 4, status: 'AVAILABLE' },
    { id: 'table-b4', name: 'B4', capacity: 4, status: 'AVAILABLE' },
    { id: 'table-c1', name: 'C1', capacity: 6, status: 'AVAILABLE' },
    { id: 'table-c2', name: 'C2', capacity: 6, status: 'AVAILABLE' },
  ],
  waitlist: [
    {
      id: 'entry-001',
      queue_number: 'A001',
      full_queue_number: 'A-20260910-001',
      phone: '0912-345-678',
      party_size: 2,
      status: 'SEATED',
      table_id: 'table-b1',
    },
    {
      id: 'entry-002',
      queue_number: 'A002',
      full_queue_number: 'A-20260910-002',
      phone: '0923-456-789',
      party_size: 4,
      status: 'WAITING',
      table_id: null,
    },
    {
      id: 'entry-003',
      queue_number: 'A003',
      full_queue_number: 'A-20260910-003',
      phone: '0934-567-890',
      party_size: 2,
      status: 'WAITING',
      table_id: null,
    },
    {
      id: 'entry-004',
      queue_number: 'A004',
      full_queue_number: 'A-20260910-004',
      phone: '0945-678-901',
      party_size: 6,
      status: 'CALLED',
      table_id: null,
    },
    {
      id: 'entry-005',
      queue_number: 'A005',
      full_queue_number: 'A-20260910-005',
      phone: '0956-789-012',
      party_size: 2,
      status: 'WAITING',
      table_id: null,
    },
    {
      id: 'entry-006',
      queue_number: 'A006',
      full_queue_number: 'A-20260910-006',
      phone: '0967-890-123',
      party_size: 4,
      status: 'WAITING',
      table_id: null,
    },
    {
      id: 'entry-007',
      queue_number: 'A007',
      full_queue_number: 'A-20260910-007',
      phone: '0978-901-234',
      party_size: 2,
      status: 'WAITING',
      table_id: null,
    },
    {
      id: 'entry-008',
      queue_number: 'A008',
      full_queue_number: 'A-20260910-008',
      phone: '0989-012-345',
      party_size: 4,
      status: 'WAITING',
      table_id: null,
    },
    {
      id: 'entry-009',
      queue_number: 'A009',
      full_queue_number: 'A-20260910-009',
      phone: '0990-123-456',
      party_size: 2,
      status: 'WAITING',
      table_id: null,
    },
  ],
};
