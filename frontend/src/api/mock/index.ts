import { seedData } from './seed';

// Mock request handlers - keyed by method:path
export const mockHandlers = new Map<string, (body?: unknown) => Promise<unknown>>();

// Simulate network latency
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// Helper to get current date in format YYYYMMDD
const getBusinessDate = (): string => {
  const now = new Date();
  return now.toISOString().slice(0, 10).replace(/-/g, '');
};

// Initialize mock handlers
function initMockHandlers(): void {
  // Public endpoints
  mockHandlers.set('GET:/api/v1/public/branches/:id', async () => {
    await delay(100);
    return {
      id: seedData.branch.id,
      name: seedData.branch.name,
      restaurant_id: seedData.restaurant.id,
      timezone: seedData.branch.timezone,
      cutoff_hour: seedData.branch.cutoff_hour,
    };
  });

  mockHandlers.set('GET:/api/v1/public/board/:id', async () => {
    await delay(100);
    const waiting = seedData.waitlist.filter((e) => e.status === 'WAITING');
    const called = seedData.waitlist.filter((e) => e.status === 'CALLED');
    return {
      branch_id: seedData.branch.id,
      current_call: called.length > 0 ? called[0] : null,
      next_up: waiting.length > 0 ? waiting[0] : null,
      recent_calls: seedData.waitlist.filter((e) => e.status === 'SEATED').slice(0, 5),
      waiting_count: waiting.length,
    };
  });

  mockHandlers.set('POST:/api/v1/public/waitlist', async (body) => {
    await delay(200);
    const data = body as { phone: string; party_size: number; name?: string };
    const seq = seedData.waitlist.length + 1;
    const date = getBusinessDate();
    const newEntry = {
      id: `entry-${String(seq).padStart(3, '0')}`,
      queue_number: `A${String(seq).padStart(3, '0')}`,
      full_queue_number: `A-${date}-${String(seq).padStart(3, '0')}`,
      phone: data.phone,
      party_size: data.party_size,
      status: 'WAITING',
      table_id: null,
    };
    seedData.waitlist.push(newEntry);
    return { ...newEntry, created_at: new Date().toISOString() };
  });

  mockHandlers.set('GET:/api/v1/public/waitlist/:queueNumber', async () => {
    await delay(100);
    const entry = seedData.waitlist.find((e) => e.queue_number.includes('A0'));
    return entry || null;
  });

  mockHandlers.set('POST:/api/v1/public/waitlist/:queueNumber/cancel', async () => {
    await delay(200);
    return { success: true };
  });

  // Auth endpoints
  mockHandlers.set('POST:/api/v1/staff/login', async (body) => {
    await delay(200);
    const data = body as { pin: string };
    if (data.pin === seedData.restaurant.pin) {
      return {
        token: 'mock-jwt-token-1234',
        staff_id: 'staff-001',
        expires_at: new Date(Date.now() + 3600000).toISOString(),
      };
    }
    throw { code: 'AUTH_INVALID_PIN', message: 'Invalid PIN' };
  });

  mockHandlers.set('POST:/api/v1/staff/pin/change', async () => {
    await delay(200);
    return { success: true };
  });

  // Staff waitlist endpoints
  mockHandlers.set('GET:/api/v1/staff/waitlist', async () => {
    await delay(100);
    return seedData.waitlist;
  });

  mockHandlers.set('POST:/api/v1/staff/waitlist/:id/call', async () => {
    await delay(200);
    return { success: true };
  });

  mockHandlers.set('POST:/api/v1/staff/waitlist/:id/seat', async () => {
    await delay(200);
    return { success: true };
  });

  mockHandlers.set('POST:/api/v1/staff/waitlist/:id/no-show', async () => {
    await delay(200);
    return { success: true };
  });

  mockHandlers.set('POST:/api/v1/staff/waitlist/:id/restore', async () => {
    await delay(200);
    return { success: true };
  });

  mockHandlers.set('POST:/api/v1/staff/waitlist/:id/revert', async () => {
    await delay(200);
    return { success: true };
  });

  mockHandlers.set('POST:/api/v1/staff/waitlist/:id/cancel', async () => {
    await delay(200);
    return { success: true };
  });

  mockHandlers.set('PATCH:/api/v1/staff/waitlist/:id', async () => {
    await delay(200);
    return { success: true };
  });

  mockHandlers.set('POST:/api/v1/staff/waitlist/reorder', async () => {
    await delay(200);
    return { success: true };
  });

  // Tables endpoints
  mockHandlers.set('GET:/api/v1/staff/tables', async () => {
    await delay(100);
    return seedData.tables;
  });

  mockHandlers.set('PATCH:/api/v1/staff/tables/:id/status', async () => {
    await delay(200);
    return { success: true };
  });

  mockHandlers.set('POST:/api/v1/staff/tables/:id/release', async () => {
    await delay(200);
    return { success: true };
  });

  // Dashboard endpoint
  mockHandlers.set('GET:/api/v1/staff/dashboard', async () => {
    await delay(100);
    return {
      branch_id: seedData.branch.id,
      total_tables: seedData.tables.length,
      available_tables: seedData.tables.filter((t) => t.status === 'AVAILABLE').length,
      occupied_tables: seedData.tables.filter((t) => t.status === 'OCCUPIED').length,
      waiting_count: seedData.waitlist.filter((e) => e.status === 'WAITING').length,
      called_count: seedData.waitlist.filter((e) => e.status === 'CALLED').length,
    };
  });

  // Settings endpoints
  mockHandlers.set('GET:/api/v1/staff/settings', async () => {
    await delay(100);
    return {
      branch_id: seedData.branch.id,
      waitlist_enabled: true,
      call_timeout_minutes: 15,
      queue_prefix: 'A',
    };
  });

  mockHandlers.set('PATCH:/api/v1/staff/settings', async () => {
    await delay(200);
    return { success: true };
  });

  // Admin endpoints
  mockHandlers.set('GET:/api/v1/admin/tables', async () => {
    await delay(100);
    return seedData.tables;
  });

  mockHandlers.set('POST:/api/v1/admin/tables', async () => {
    await delay(200);
    return { success: true };
  });

  mockHandlers.set('PUT:/api/v1/admin/tables/:id', async () => {
    await delay(200);
    return { success: true };
  });

  mockHandlers.set('DELETE:/api/v1/admin/tables/:id', async () => {
    await delay(200);
    return { success: true };
  });

  mockHandlers.set('POST:/api/v1/admin/reset', async () => {
    await delay(200);
    return { success: true };
  });
}

// Initialize handlers on first import
initMockHandlers();

export { seedData };
