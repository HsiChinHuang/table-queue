/**
 * Shared test fixtures (F-15, _docs/testing.md section 5).
 * Shapes mirror the kit's own response interfaces (api/public.ts, api/dashboard.ts,
 * api/tables.ts) and the component data interfaces (components/WaitlistCard.tsx,
 * components/TableCard.tsx), so a fixture can feed either the API layer or a component prop
 * without a cast. Plain deterministic data only: no functions, no clocks.
 */

import type { BoardResponse, PublicBranch, WaitlistEntry as PublicWaitlistEntry } from '@/api/public';
import type { DashboardResponse } from '@/api/dashboard';
import type { Table } from '@/api/tables';

/** Component-shaped waitlist entry (components/WaitlistCard.tsx WaitlistEntry). */
export const mockWaitlistEntry = {
  id: 1,
  queueNumber: 'A001',
  name: 'Alice Chen',
  phone: '0912-345-678',
  partySize: 4,
  status: 'WAITING',
  note: 'Window seat if possible',
  waitMinutes: 12,
  holdMinutes: 15,
  targetTime: 1_800_000,
} as const;

/** Component-shaped table (components/TableCard.tsx TableData). */
export const mockTable = {
  id: 7,
  label: 'B2',
  capacity: 6,
  status: 'OCCUPIED',
  occupiedBy: {
    queueNumber: 'A001',
    partySize: 4,
    targetTime: 1_800_000,
  },
} as const;

/** API-shaped public branch (api/public.ts PublicBranch). */
export const mockBranch: PublicBranch = {
  id: 'branch-001',
  name: 'Main Branch',
  restaurant_id: 'rest-001',
  timezone: 'Asia/Taipei',
  cutoff_hour: 22,
  restaurant_name: 'Testaurant',
  branch_name: 'Main Branch',
  hours: '11:00 - 22:00',
  waiting_count: 3,
  is_waitlist_open: true,
};

/** API-shaped dashboard (api/dashboard.ts DashboardResponse). */
export const mockDashboard: DashboardResponse = {
  branch_id: 'branch-001',
  total_tables: 12,
  available_tables: 8,
  occupied_tables: 4,
  waiting_count: 3,
  called_count: 1,
};

/** API-shaped board (api/public.ts BoardResponse). */
export const mockBoard: BoardResponse = {
  branch_id: 'branch-001',
  current_call: mockApiEntry('A001', 'CALLED'),
  next_up: mockApiEntry('A002', 'WAITING'),
  recent_calls: [mockApiEntry('A000', 'SEATED')],
  waiting_count: 3,
};

/** API-shaped table row (api/tables.ts Table). */
export const mockApiTable: Table = {
  id: 't7',
  name: 'B2',
  capacity: 6,
  status: 'CLEANING',
};

/** Build one api-shaped waitlist entry (api/public.ts WaitlistEntry). */
export function mockApiEntry(queueNumber: string, status: string): PublicWaitlistEntry {
  return {
    id: `id-${queueNumber}`,
    queue_number: queueNumber,
    full_queue_number: `A-${queueNumber}`,
    phone: '0912-345-678',
    party_size: 4,
    status,
    table_id: null,
  };
}
