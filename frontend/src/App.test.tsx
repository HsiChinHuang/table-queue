// @vitest-environment jsdom
/**
 * App mount test - verifies that the real page components are mounted
 * instead of placeholder stubs. This is the core D0 integration test.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
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

function createWrapper() {
  const queryClient = new QueryClient({
    logger: {
      log: () => {},
      warn: () => {},
      error: () => {},
    },
    defaultOptions: {
      queries: {
        retry: false,
        suspense: false,
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
});

describe('App shell mounts real page components', () => {
  it('renders JoinPage at /join (not placeholder)', async () => {
    render(
      <MemoryRouter initialEntries={['/join']}>
        <App />
      </MemoryRouter>,
      { wrapper: createWrapper() }
    );

    // Wait for the page to render
    await waitFor(() => {
      // JoinPage should have form fields, not placeholder text
      expect(screen.getByText(/Join the Waitlist/i)).toBeTruthy();
      expect(screen.getByLabelText(/Name/i)).toBeTruthy();
      expect(screen.getByLabelText(/Phone/i)).toBeTruthy();
    });

    // Ensure placeholder text is NOT present
    expect(screen.queryByText(/JoinPage/i)).toBeNull();
  });

  it('renders StatusPage at /status/A001?token=123 (not placeholder)', async () => {
    render(
      <MemoryRouter initialEntries={['/status/A001?token=123']}>
        <App />
      </MemoryRouter>,
      { wrapper: createWrapper() }
    );

    // StatusPage shows the queue number
    await waitFor(() => {
      expect(screen.getByText('A001')).toBeTruthy();
    });

    // Ensure placeholder text is NOT present
    expect(screen.queryByText(/StatusPage/i)).toBeNull();
  });

  it('renders LookupPage at /lookup (not placeholder)', async () => {
    render(
      <MemoryRouter initialEntries={['/lookup']}>
        <App />
      </MemoryRouter>,
      { wrapper: createWrapper() }
    );

    // LookupPage should have lookup form
    await waitFor(() => {
      expect(screen.getByText(/Check Your Status/i)).toBeTruthy();
      expect(screen.getByLabelText(/Queue Number/i)).toBeTruthy();
    });

    // Ensure placeholder text is NOT present
    expect(screen.queryByText(/LookupPage/i)).toBeNull();
  });

  it('renders LoginPage at /staff/login (not placeholder)', async () => {
    // Clear token to see login page
    useStaffStore.getState().clearToken();
    
    render(
      <MemoryRouter initialEntries={['/staff/login']}>
        <App />
      </MemoryRouter>,
      { wrapper: createWrapper() }
    );

    // LoginPage should have PIN input
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Enter your PIN/i)).toBeTruthy();
      expect(screen.getByText(/Staff Login/i)).toBeTruthy();
    });

    // Ensure placeholder text is NOT present
    expect(screen.queryByText(/StaffLoginPage/i)).toBeNull();
  });

  it('renders WaitlistPage at /staff/waitlist (not placeholder)', async () => {
    render(
      <MemoryRouter initialEntries={['/staff/waitlist']}>
        <App />
      </MemoryRouter>,
      { wrapper: createWrapper() }
    );

    // WaitlistPage should have stats or waitlist section
    await waitFor(() => {
      // The page should render without throwing (QueryClientProvider is set)
      // Look for any real content - stats cards or empty state
      const body = screen.getByText(/Active Waitlist/i) || 
                   screen.getByText(/Waiting/i) ||
                   screen.getByText(/No one is waiting/i);
      expect(body).toBeTruthy();
    });

    // Ensure placeholder text is NOT present
    expect(screen.queryByText(/StaffWaitlistPage/i)).toBeNull();
  });

  it('renders TablesPage at /staff/tables (not placeholder)', async () => {
    render(
      <MemoryRouter initialEntries={['/staff/tables']}>
        <App />
      </MemoryRouter>,
      { wrapper: createWrapper() }
    );

    // TablesPage should show tables or empty state
    await waitFor(() => {
      // Look for any real content
      const body = screen.getByText(/No tables yet/i) || 
                   screen.getByText(/pax/i) ||
                   screen.getByText(/Available/i);
      expect(body).toBeTruthy();
    });

    // Ensure placeholder text is NOT present
    expect(screen.queryByText(/StaffTablesPage/i)).toBeNull();
  });
});
