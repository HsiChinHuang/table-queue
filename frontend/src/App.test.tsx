// @vitest-environment jsdom
/**
 * App mount test - verifies that the real page components are mounted
 * instead of placeholder stubs. This is the core D0 integration test.
 * 
 * LIMITATION: Staff waitlist/tables routes are NOT tested here due to
 * jsdom refetch-interval teardown hang (orchestrator reproduced: 3 fake-timer
 * variants all rc=124). Staff guard redirect is verified. Mount coverage for
 * those routes comes from the headless-DOM AC-9 mechanism. The existing staff
 * 'tests' are pure-function (no render) and do NOT cover mounting.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createAppRouter } from './App';
import { useStaffStore } from '@/api/staffStore';

// Mock API calls that pages make
vi.mock('@/api/public', () => ({
  getBoard: vi.fn().mockResolvedValue({
    branch_id: 'branch-001',
    waiting_count: 0,
    current_call: null,
    next_up: null,
    recent_calls: [],
  }),
  getPublicBranch: vi.fn().mockResolvedValue({
    id: 'branch-001',
    name: 'Main Branch',
    restaurant_id: 'rest-001',
    timezone: 'Asia/Taipei',
    cutoff_hour: 22,
    restaurant_name: 'Testaurant',
    branch_name: 'Main Branch',
    hours: '11:00 - 22:00',
    waiting_count: 0,
    is_waitlist_open: true,
  }),
  getStatus: vi.fn().mockResolvedValue({
    id: 'test-id',
    queue_number: 'A001',
    full_queue_number: 'A-20260910-001',
    phone: '0912-345-678',
    party_size: 2,
    status: 'WAITING',
    table_id: null,
  }),
  joinWaitlist: vi.fn(),
  cancelWaitlist: vi.fn(),
}));

vi.mock('@/api/waitlist', () => ({
  listWaitlist: vi.fn().mockResolvedValue([]),
  callWaitlist: vi.fn(),
  seatWaitlist: vi.fn(),
  noShowWaitlist: vi.fn(),
  restoreWaitlist: vi.fn(),
  revertWaitlist: vi.fn(),
  cancelWaitlistByStaff: vi.fn(),
  reorderWaitlist: vi.fn(),
}));

vi.mock('@/api/dashboard', () => ({
  getDashboard: vi.fn().mockResolvedValue({
    branch_id: 'branch-001',
    total_tables: 12,
    available_tables: 8,
    occupied_tables: 4,
    waiting_count: 0,
    called_count: 0,
  }),
}));

vi.mock('@/api/tables', () => ({
  listTables: vi.fn().mockResolvedValue([]),
  updateTableStatus: vi.fn(),
  releaseTable: vi.fn(),
}));

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  changePin: vi.fn(),
}));

vi.mock('@/api/admin', () => ({
  getSettings: vi.fn().mockResolvedValue({
    branch_id: 'branch-001',
    call_timeout_minutes: 15,
    hold_time_minutes: 10,
    max_party_size: 10,
  }),
}));

// Mock hooks that pages use (usePublicBranch, etc.)
vi.mock('@/api/hooks', () => ({
  usePublicBranch: vi.fn(() => ({
    data: {
      id: 'branch-001',
      name: 'Main Branch',
      restaurant_id: 'rest-001',
      timezone: 'Asia/Taipei',
      cutoff_hour: 22,
      restaurant_name: 'Testaurant',
      branch_name: 'Main Branch',
      hours: '11:00 - 22:00',
      waiting_count: 0,
      is_waitlist_open: true,
    },
    isLoading: false,
    isError: false,
    error: null,
  })),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}

beforeEach(() => {
  // Set a token so StaffLayout doesn't redirect to login
  useStaffStore.getState().setToken('test-token');
  vi.clearAllMocks();
});

afterEach(() => {
  useStaffStore.getState().clearToken();
  vi.clearAllMocks();
  cleanup();
});

describe('App shell mounts real page components', () => {
  it('renders JoinPage at /join (not placeholder)', async () => {
    const router = createAppRouter('/join');
    const { unmount } = render(
      <RouterProvider router={router} />,
      { wrapper: createWrapper() }
    );

    // Wait for the page to render
    await screen.findByText(/Join the Waitlist/i, undefined, { timeout: 5000 });
    await screen.findByLabelText(/Name/i, undefined, { timeout: 5000 });
    await screen.findByLabelText(/Phone/i, undefined, { timeout: 5000 });

    // Ensure placeholder text is NOT present
    expect(screen.queryByText(/JoinPage/i)).toBeNull();
    
    // Clean up to stop any intervals/timers
    unmount();
  });

  it('renders StatusPage at /status/A001?token=123 (not placeholder)', async () => {
    const router = createAppRouter('/status/A001?token=123');
    const { unmount } = render(
      <RouterProvider router={router} />,
      { wrapper: createWrapper() }
    );

    // StatusPage shows the queue number
    await screen.findByText('A001', undefined, { timeout: 5000 });

    // Ensure placeholder text is NOT present
    expect(screen.queryByText(/StatusPage/i)).toBeNull();
    
    unmount();
  });

  it('renders LookupPage at /lookup (not placeholder)', async () => {
    const router = createAppRouter('/lookup');
    const { unmount } = render(
      <RouterProvider router={router} />,
      { wrapper: createWrapper() }
    );

    // LookupPage should have lookup form
    await screen.findByText(/Check Your Status/i, undefined, { timeout: 5000 });
    await screen.findByLabelText(/Queue Number/i, undefined, { timeout: 5000 });

    // Ensure placeholder text is NOT present
    expect(screen.queryByText(/LookupPage/i)).toBeNull();
    
    unmount();
  });

  it('renders LoginPage at /staff/login (not placeholder)', async () => {
    // Clear token to see login page
    useStaffStore.getState().clearToken();
    
    const router = createAppRouter('/staff/login');
    const { unmount } = render(
      <RouterProvider router={router} />,
      { wrapper: createWrapper() }
    );

    // LoginPage should have PIN input
    await screen.findByPlaceholderText(/Enter your PIN/i, undefined, { timeout: 5000 });
    await screen.findByText(/Staff Login/i, undefined, { timeout: 5000 });

    // Ensure placeholder text is NOT present
    expect(screen.queryByText(/StaffLoginPage/i)).toBeNull();
    
    unmount();
  });
});
