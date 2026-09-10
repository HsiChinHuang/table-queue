// @vitest-environment jsdom
/**
 * Tests for TablesPage.
 * AC-10: formatOccupiedLabel tests and page behavior tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { Mock } from 'vitest';
import { render, fireEvent, waitFor, screen, within, cleanup } from '@testing-library/react';
import type { RenderResult } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TablesPage, { formatOccupiedLabel } from './TablesPage';
import { staffStore } from '@/stores/staffStore';

// Mock hooks - must be before import
vi.mock('@/api/queryKeys', () => ({
  tables: vi.fn((branchId) => ['tables', branchId]),
  tablesKeys: {
    all: ['tables'],
    list: vi.fn((branchId) => ['tables', 'list', branchId]),
  },
}));

vi.mock('@/api/tables', () => ({
  listTables: vi.fn(),
  updateTableStatus: vi.fn(),
  releaseTable: vi.fn(),
}));

vi.mock('@/stores/staffStore', () => ({
  staffStore: {
    getState: vi.fn(() => ({ branchId: 1 })),
    setState: vi.fn(),
  },
}));

// Mock @tanstack/react-query
vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-query')>();
  return {
    ...actual,
    useQuery: vi.fn(),
    useMutation: vi.fn(),
    useQueryClient: vi.fn(() => ({
      invalidateQueries: vi.fn(),
    })),
  };
});

import { useQuery, useMutation } from '@tanstack/react-query';

// Loosened mock signatures: the page calls these hooks with many different
// generic instantiations across tests, so the mocks are typed loosely on purpose.
const mockUseQuery = vi.mocked(useQuery) as unknown as Mock<
  (...args: unknown[]) => Record<string, unknown>
>;
const mockUseMutation = vi.mocked(useMutation) as unknown as Mock<
  (...args: unknown[]) => Record<string, unknown>
>;

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  (vi.mocked(staffStore.getState) as unknown as Mock<() => Record<string, unknown>>).mockReturnValue({
    branchId: 1,
  });
});

afterEach(() => {
  currentView?.unmount();
  currentView = null;
  cleanup();
  vi.clearAllMocks();
});

let currentView: RenderResult | null = null;

function renderWithProvider(ui: React.ReactElement) {
  currentView?.unmount();
  const view = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/staff/tables']}>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>
  );
  currentView = view;
  return view;
}

describe('formatOccupiedLabel', () => {
  it('should format occupied label correctly for 25 minutes', () => {
    const result = formatOccupiedLabel({
      queueNumber: 'A012',
      partySize: 4,
      occupiedMinutes: 25,
    });
    expect(result).toBe('A012 · 4 pax · 25 min');
  });

  it('should format occupied label correctly for 0 minutes', () => {
    const result = formatOccupiedLabel({
      queueNumber: 'A001',
      partySize: 2,
      occupiedMinutes: 0,
    });
    expect(result).toBe('A001 · 2 pax · 0 min');
  });

  it('should handle different queue number formats', () => {
    const result = formatOccupiedLabel({
      queueNumber: 'B001',
      partySize: 6,
      occupiedMinutes: 15,
    });
    expect(result).toBe('B001 · 6 pax · 15 min');
  });

  it('should handle large party sizes', () => {
    const result = formatOccupiedLabel({
      queueNumber: 'C025',
      partySize: 20,
      occupiedMinutes: 45,
    });
    expect(result).toBe('C025 · 20 pax · 45 min');
  });
});

describe('TablesPage - empty state', () => {
  it('renders empty state when tables array is empty', () => {
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    renderWithProvider(<TablesPage />);
    
    expect(screen.getByText('No tables yet. Add tables in Settings.')).toBeTruthy();
  });

  it('renders Store icon in empty state', () => {
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    const { container } = renderWithProvider(<TablesPage />);
    
    expect(container.querySelector('svg')).toBeTruthy();
  });
});

describe('TablesPage - grid rendering', () => {
  it('renders grid with correct number of table cards', () => {
    const mockTables = [
      { id: '1', label: 'A01', capacity: 2, status: 'AVAILABLE' },
      { id: '2', label: 'A02', capacity: 4, status: 'AVAILABLE' },
      { id: '3', label: 'A03', capacity: 6, status: 'AVAILABLE' },
      { id: '4', label: 'A04', capacity: 8, status: 'AVAILABLE' },
    ];

    vi.mocked(mockUseQuery).mockReturnValue({
      data: mockTables,
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    renderWithProvider(<TablesPage />);
    
    // Check all table labels exist
    expect(screen.getAllByText(/A01|A02|A03|A04/).length).toBe(4);
  });

  it('renders grid layout classes', () => {
    const mockTables = [
      { id: '1', label: 'A01', capacity: 2, status: 'AVAILABLE' },
    ];

    vi.mocked(mockUseQuery).mockReturnValue({
      data: mockTables,
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    const { container } = renderWithProvider(<TablesPage />);
    
    const grid = container.querySelector('.grid');
    expect(grid).toBeTruthy();
    const classes = grid?.className ?? '';
    expect(classes.includes('grid-cols-2')).toBe(true);
    expect(classes.includes('md:grid-cols-3')).toBe(true);
    expect(classes.includes('lg:grid-cols-4')).toBe(true);
  });
});

describe('TablesPage - AVAILABLE table toggle', () => {
  it('triggers updateTableStatus mutation when AVAILABLE table is clicked', () => {
    const mockMutate = vi.fn();
    
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [{ id: '1', label: 'A01', capacity: 2, status: 'AVAILABLE' }],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: mockMutate,
      isLoading: false,
    });

    const { getByRole } = renderWithProvider(<TablesPage />);
    
    const tableCard = getByRole('button', { name: /table a01, 2 pax, available/i });
    fireEvent.click(tableCard);
    
    expect(mockMutate).toHaveBeenCalledWith({
      tableId: '1',
      status: 'CLEANING',
    });
  });

  it('toggles AVAILABLE to CLEANING', () => {
    const mockMutate = vi.fn();
    
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [{ id: '1', label: 'A01', capacity: 2, status: 'AVAILABLE' }],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: mockMutate,
      isLoading: false,
    });

    const { getByRole } = renderWithProvider(<TablesPage />);
    
    const tableCard = getByRole('button', { name: /table a01, 2 pax, available/i });
    fireEvent.click(tableCard);
    
    expect(mockMutate).toHaveBeenCalledWith({
      tableId: '1',
      status: 'CLEANING',
    });
  });
});

describe('TablesPage - CLEANING table toggle', () => {
  it('triggers updateTableStatus mutation when CLEANING table is clicked', () => {
    const mockMutate = vi.fn();
    
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [{ id: '1', label: 'A01', capacity: 2, status: 'CLEANING' }],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: mockMutate,
      isLoading: false,
    });

    const { getByRole } = renderWithProvider(<TablesPage />);
    
    const tableCard = getByRole('button', { name: /table a01, 2 pax, cleaning/i });
    fireEvent.click(tableCard);
    
    expect(mockMutate).toHaveBeenCalledWith({
      tableId: '1',
      status: 'AVAILABLE',
    });
  });

  it('toggles CLEANING to AVAILABLE', () => {
    const mockMutate = vi.fn();
    
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [{ id: '1', label: 'A01', capacity: 2, status: 'CLEANING' }],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: mockMutate,
      isLoading: false,
    });

    const { getByRole } = renderWithProvider(<TablesPage />);
    
    const tableCard = getByRole('button', { name: /table a01, 2 pax, cleaning/i });
    fireEvent.click(tableCard);
    
    expect(mockMutate).toHaveBeenCalledWith({
      tableId: '1',
      status: 'AVAILABLE',
    });
  });
});

describe('TablesPage - OCCUPIED table', () => {
  it('shows occupied label with formatOccupiedLabel format', () => {
    const mockTables = [
      {
        id: '1',
        label: 'A01',
        capacity: 4,
        status: 'OCCUPIED',
        occupiedBy: {
          queueNumber: 'A012',
          partySize: 4,
          occupiedMinutes: 25,
        },
      },
    ];

    vi.mocked(mockUseQuery).mockReturnValue({
      data: mockTables,
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    renderWithProvider(<TablesPage />);
    
    expect(screen.getByText('A012 · 4 pax · 25 min')).toBeTruthy();
  });

  it('shows Release Table button for OCCUPIED tables', () => {
    const mockTables = [
      {
        id: '1',
        label: 'A01',
        capacity: 4,
        status: 'OCCUPIED',
        occupiedBy: {
          queueNumber: 'A001',
          partySize: 2,
          occupiedMinutes: 10,
        },
      },
    ];

    vi.mocked(mockUseQuery).mockReturnValue({
      data: mockTables,
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    const { getByRole } = renderWithProvider(<TablesPage />);
    
    expect(getByRole('button', { name: /release table a01/i })).toBeTruthy();
  });

  it('opens confirmation dialog when Release Table is clicked', async () => {
    const mockTables = [
      {
        id: '1',
        label: 'A01',
        capacity: 4,
        status: 'OCCUPIED',
        occupiedBy: {
          queueNumber: 'A001',
          partySize: 2,
          occupiedMinutes: 10,
        },
      },
    ];

    vi.mocked(mockUseQuery).mockReturnValue({
      data: mockTables,
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    const { getByRole } = renderWithProvider(<TablesPage />);
    
    const releaseButton = getByRole('button', { name: /release table a01/i });
    fireEvent.click(releaseButton);
    
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeTruthy();
    });
    expect(
      within(screen.getByRole('dialog')).getByText(/Are you sure you want to release this table/)
    ).toBeTruthy();
  });
});

describe('TablesPage - Release Table confirmation', () => {
  it('triggers releaseTable mutation when confirmation is confirmed', async () => {
    const mockMutate = vi.fn();
    
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [{
        id: '1',
        label: 'A01',
        capacity: 4,
        status: 'OCCUPIED',
        occupiedBy: {
          queueNumber: 'A001',
          partySize: 2,
          occupiedMinutes: 10,
        },
      }],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: mockMutate,
      isLoading: false,
    });

    const { getByRole } = renderWithProvider(<TablesPage />);
    
    const releaseButton = getByRole('button', { name: /release table a01/i });
    fireEvent.click(releaseButton);
    
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeTruthy();
    });

    const confirmButton = within(screen.getByRole('dialog')).getByRole('button', {
      name: /release/i,
    });
    fireEvent.click(confirmButton);
    
    expect(mockMutate).toHaveBeenCalledWith({
      tableId: '1',
    });
  });

  it('closes dialog when cancel is clicked', async () => {
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [{
        id: '1',
        label: 'A01',
        capacity: 4,
        status: 'OCCUPIED',
        occupiedBy: {
          queueNumber: 'A001',
          partySize: 2,
          occupiedMinutes: 10,
        },
      }],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    const { getByRole } = renderWithProvider(<TablesPage />);
    
    const releaseButton = getByRole('button', { name: /release table a01/i });
    fireEvent.click(releaseButton);
    
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeTruthy();
    });

    const cancelButton = within(screen.getByRole('dialog')).getByRole('button', {
      name: /cancel/i,
    });
    fireEvent.click(cancelButton);
    
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull();
    });
  });
});

describe('TablesPage - status colors', () => {
  it('displays AVAILABLE status with green color', () => {
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [{ id: '1', label: 'A01', capacity: 2, status: 'AVAILABLE' }],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    const { container } = renderWithProvider(<TablesPage />);
    
    const badge = container.querySelector('.bg-AVAILABLE');
    expect(badge).toBeTruthy();
  });

  it('displays OCCUPIED status with orange color', () => {
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [{
        id: '1',
        label: 'A01',
        capacity: 4,
        status: 'OCCUPIED',
        occupiedBy: {
          queueNumber: 'A001',
          partySize: 2,
          occupiedMinutes: 10,
        },
      }],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    const { container } = renderWithProvider(<TablesPage />);
    
    const badge = container.querySelector('.bg-OCCUPIED');
    expect(badge).toBeTruthy();
  });

  it('displays CLEANING status with purple color', () => {
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [{ id: '1', label: 'A01', capacity: 2, status: 'CLEANING' }],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    const { container } = renderWithProvider(<TablesPage />);
    
    const badge = container.querySelector('.bg-CLEANING');
    expect(badge).toBeTruthy();
  });
});

describe('TablesPage - card fields', () => {
  it('displays table label', () => {
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [{ id: '1', label: 'A01', capacity: 2, status: 'AVAILABLE' }],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    const { container } = renderWithProvider(<TablesPage />);
    
    // Find the table label span
    const label = container.querySelector('.text-lg.font-bold');
    expect(label?.textContent).toBe('A01');
  });

  it('displays table capacity', () => {
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [{ id: '1', label: 'A01', capacity: 4, status: 'AVAILABLE' }],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    const { container } = renderWithProvider(<TablesPage />);
    
    // Find capacity text
    const capacityText = container.querySelectorAll('.text-sm.text-text-secondary');
    expect(capacityText.length).toBeGreaterThan(0);
    expect(capacityText[0]?.textContent).toBe('4 pax');
  });

  it('displays status badge text for CLEANING', () => {
    vi.mocked(mockUseQuery).mockReturnValue({
      data: [{ id: '1', label: 'A01', capacity: 2, status: 'CLEANING' }],
      isLoading: false,
      error: null,
    });
    
    vi.mocked(mockUseMutation).mockReturnValue({
      mutate: vi.fn(),
      isLoading: false,
    });

    const { container } = renderWithProvider(<TablesPage />);
    
    const badge = container.querySelector('.bg-CLEANING');
    expect(badge).toBeTruthy();
    expect(badge?.textContent).toBe('Cleaning');
  });
});
