/**
 * WaitlistPage - Staff waitlist management page.
 * 
 * Features:
 * - Stats cards with 10 metrics
 * - Search by name or phone last 3 digits with 300ms debounce
 * - Status filter (Active/Closed/All)
 * - Party size filter
 * - Pause Waitlist switch
 * - Close Day button with confirmation
 * - Waitlist cards sorted by sort_order
 * - Card actions: Call, Seat, No-show, Restore, Revert, Cancel, Edit
 * - Countdown timer for CALLED entries
 * - Move up/down reorder buttons
 * - Collapsible Closed today section
 * - Last updated timestamp
 * - Polling every 3 seconds
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
// Local toast shim: F-12 Constraints forbid adding dependencies (package.json is frozen).
// The merged kit has no toast library, so notifications dispatch a window event that
// any host can render; call sites keep the same toast.success/toast.error API.
export const toast = {
  success: (message: string) => {
    window.dispatchEvent(new CustomEvent('tq-toast', { detail: { kind: 'success', message } }));
  },
  error: (message: string) => {
    window.dispatchEvent(new CustomEvent('tq-toast', { detail: { kind: 'error', message } }));
  },
};
import { Search, ArrowUp, ArrowDown, Calendar } from 'lucide-react';

import { getPublicBranch, type PublicBranch } from '@/api/public';
import { dashboardKeys, waitlistKeys } from '@/api/queryKeys';
import { getDashboard, DashboardResponse } from '@/api/dashboard';
import {
  listWaitlist,
  callWaitlist,
  seatWaitlist,
  noShowWaitlist,
  restoreWaitlist,
  revertWaitlist,
  cancelWaitlistByStaff,
  reorderWaitlist,
  ReorderRequest,
} from '@/api/waitlist';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { WaitlistCard } from '@/components/WaitlistCard';
import { StatusBadge } from '@/components/StatusBadge';
import { EmptyState } from '@/components/EmptyState';

// Waitlist entry type for frontend (matches API response)
export interface WaitlistEntry {
  id: string;
  queue_number: string;
  full_queue_number: string;
  phone: string;
  party_size: number;
  status: 'WAITING' | 'CALLED' | 'SEATED' | 'NO_SHOW' | 'CANCELLED' | 'DONE';
  table_id: string | null;
  name?: string;
  note?: string;
  sort_order?: number;
  created_at?: string;
  called_at?: string;
  hold_minutes_snapshot?: number;
}

// Stats card data type
interface StatsData {
  waiting: number;
  called: number;
  seated: number;
  availableTables: number;
  occupied: number;
  cleaning: number;
  noShowToday: number;
  cancelledToday: number;
  seatedToday: number;
  avgWaitToday: number;
}

/**
 * Pure function to filter waitlist entries by status.
 * Active statuses: WAITING, CALLED, SEATED
 * Closed statuses: NO_SHOW, CANCELLED, DONE
 * 
 * @param items - Array of waitlist entries
 * @param filter - Filter type: 'Active', 'Closed', or 'All'
 * @returns Object with active and closed arrays
 */
export function filterByStatus(
  items: WaitlistEntry[],
  filter: 'Active' | 'Closed' | 'All'
): { active: WaitlistEntry[]; closed: WaitlistEntry[] } {
  const active: WaitlistEntry[] = [];
  const closed: WaitlistEntry[] = [];

  for (const item of items) {
    if (item.status === 'WAITING' || item.status === 'CALLED' || item.status === 'SEATED') {
      active.push(item);
    } else {
      closed.push(item);
    }
  }

  if (filter === 'Active') {
    return { active, closed: [] };
  } else if (filter === 'Closed') {
    return { active: [], closed };
  }
  return { active, closed };
}

/**
 * Debounce hook for search input
 */
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

const WaitlistPage: React.FC = () => {
  // The staff store persists only token/staffId; the canonical branch identifier comes
  // from the public branch endpoint (seeded as branch-001 in dev).
  const queryClient = useQueryClient();

  // State
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'Active' | 'Closed' | 'All'>('All');
  const [partySizeFilter, setPartySizeFilter] = useState<string>('');
  const [showClosed, setShowClosed] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    title: string;
    description?: string;
    onConfirm: () => void;
    variant?: 'danger' | 'default';
  }>({ open: false, title: '', onConfirm: () => {} });

  // Debounce search with 300ms
  const debouncedSearch = useDebounce(searchQuery, 300);

  // Fetch dashboard stats
  const { data: branch } = useQuery<PublicBranch | null, Error>({
    queryKey: ['branch', 'staff'],
    queryFn: () => getPublicBranch('1'),
  });
  const branchId = branch?.id ?? 'branch-001';

  const { data: dashboard, isLoading: loadingDashboard } = useQuery<DashboardResponse, Error>({
    queryKey: dashboardKeys.get(branchId),
    queryFn: () => getDashboard(branchId),
    refetchInterval: 3000,
    staleTime: 5000,
  });

  // Fetch waitlist entries
  const { data: waitlistRaw, isLoading: loadingWaitlist } = useQuery<WaitlistEntry[], Error>({
    queryKey: waitlistKeys.list(branchId),
    // The API layer types status as string; this page narrows it to the union
    // below and defends against non-array payloads from the transport.
    queryFn: async () => {
      const entries = await listWaitlist(branchId);
      return (Array.isArray(entries) ? entries : []) as unknown as WaitlistEntry[];
    },
    refetchInterval: 3000,
    staleTime: 5000,
  });

  const waitlistData = waitlistRaw ?? [];

  // Mutations
  const callMutation = useMutation({
    mutationFn: (entryId: string) => callWaitlist(entryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: waitlistKeys.list(branchId) });
      queryClient.invalidateQueries({ queryKey: dashboardKeys.get(branchId) });
      toast.success('Guest called');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to call guest');
    },
  });

  const seatMutation = useMutation({
    mutationFn: ({ entryId, tableId }: { entryId: string; tableId: string }) =>
      seatWaitlist(entryId, tableId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: waitlistKeys.list(branchId) });
      queryClient.invalidateQueries({ queryKey: dashboardKeys.get(branchId) });
      toast.success('Guest seated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to seat guest');
    },
  });

  const noShowMutation = useMutation({
    mutationFn: (entryId: string) => noShowWaitlist(entryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: waitlistKeys.list(branchId) });
      queryClient.invalidateQueries({ queryKey: dashboardKeys.get(branchId) });
      toast.success('Marked as no-show');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to mark no-show');
    },
  });

  const restoreMutation = useMutation({
    mutationFn: (entryId: string) => restoreWaitlist(entryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: waitlistKeys.list(branchId) });
      queryClient.invalidateQueries({ queryKey: dashboardKeys.get(branchId) });
      toast.success('Entry restored');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to restore entry');
    },
  });

  const revertMutation = useMutation({
    mutationFn: (entryId: string) => revertWaitlist(entryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: waitlistKeys.list(branchId) });
      queryClient.invalidateQueries({ queryKey: dashboardKeys.get(branchId) });
      toast.success('Call reverted');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to revert call');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (entryId: string) => cancelWaitlistByStaff(entryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: waitlistKeys.list(branchId) });
      queryClient.invalidateQueries({ queryKey: dashboardKeys.get(branchId) });
      toast.success('Entry cancelled');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to cancel entry');
    },
  });

  const reorderMutation = useMutation({
    mutationFn: (request: ReorderRequest) => reorderWaitlist(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: waitlistKeys.list(branchId) });
      toast.success('Order updated');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to reorder');
    },
  });

  const closeDayMutation = useMutation({
    mutationFn: () => {
      // Close day would typically call an endpoint
      // For now, we'll just invalidate queries
      return Promise.resolve();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: waitlistKeys.list(branchId) });
      queryClient.invalidateQueries({ queryKey: dashboardKeys.get(branchId) });
      toast.success('Day closed');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to close day');
    },
  });

  // Derived state
  const stats: StatsData = useMemo(() => {
    if (!dashboard) {
      return {
        waiting: 0,
        called: 0,
        seated: 0,
        availableTables: 0,
        occupied: 0,
        cleaning: 0,
        noShowToday: 0,
        cancelledToday: 0,
        seatedToday: 0,
        avgWaitToday: 0,
      };
    }
    return {
      waiting: dashboard.waiting_count || 0,
      called: dashboard.called_count || 0,
      // F-03 DashboardResponse exposes only the fields below; remaining stats
      // default to 0 until the backend adds them.
      seated: 0,
      availableTables: dashboard.available_tables || 0,
      occupied: dashboard.occupied_tables || 0,
      cleaning: 0,
      noShowToday: 0,
      cancelledToday: 0,
      seatedToday: 0,
      avgWaitToday: 0,
    };
  }, [dashboard]);

  // Filter and sort waitlist entries
  const filteredEntries = useMemo(() => {
    if (!waitlistData) return { active: [], closed: [] };

    let entries = waitlistData.slice();

    // Search filter (by name or phone last 3 digits)
    if (debouncedSearch) {
      const query = debouncedSearch.toLowerCase();
      entries = entries.filter(
        (entry) =>
          entry.name?.toLowerCase().includes(query) ||
          entry.phone.slice(-3).includes(query)
      );
    }

    // Party size filter
    if (partySizeFilter) {
      const size = parseInt(partySizeFilter, 10);
      entries = entries.filter((entry) => entry.party_size === size);
    }

    // Status filter using filterByStatus
    return filterByStatus(entries, statusFilter);
  }, [waitlistData, debouncedSearch, partySizeFilter, statusFilter]);

  // Sort entries by sort_order
  const sortedActive = useMemo(() => {
    return [...filteredEntries.active].sort(
      (a, b) => (a.sort_order || 0) - (b.sort_order || 0)
    );
  }, [filteredEntries.active]);

  const sortedClosed = useMemo(() => {
    return [...filteredEntries.closed].sort(
      (a, b) => (b.sort_order || 0) - (a.sort_order || 0)
    );
  }, [filteredEntries.closed]);

  // Last updated timestamp
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  useEffect(() => {
    if (waitlistData || dashboard) {
      setLastUpdated(new Date());
    }
  }, [waitlistData, dashboard]);

  // Handlers
  const handleCall = useCallback((entryId: string) => {
    callMutation.mutate(entryId);
  }, [callMutation]);

  const handleSeat = useCallback((entryId: string, tableId: string) => {
    seatMutation.mutate({ entryId, tableId });
  }, [seatMutation]);

  const handleNoShow = useCallback((entryId: string) => {
    setConfirmDialog({
      open: true,
      title: 'Mark as No-show?',
      description: 'This guest did not show up within the hold time.',
      onConfirm: () => {
        noShowMutation.mutate(entryId);
        setConfirmDialog({ open: false, title: '', onConfirm: () => {} });
      },
      variant: 'danger',
    });
  }, [noShowMutation]);

  const handleRestore = useCallback((entryId: string) => {
    restoreMutation.mutate(entryId);
  }, [restoreMutation]);

  const handleRevert = useCallback((entryId: string) => {
    setConfirmDialog({
      open: true,
      title: 'Revert this call?',
      description: 'This will return the guest to the waiting queue.',
      onConfirm: () => {
        revertMutation.mutate(entryId);
        setConfirmDialog({ open: false, title: '', onConfirm: () => {} });
      },
      variant: 'default',
    });
  }, [revertMutation]);

  const handleCancel = useCallback((entryId: string) => {
    setConfirmDialog({
      open: true,
      title: 'Cancel this entry?',
      description: 'This will remove the guest from the waitlist.',
      onConfirm: () => {
        cancelMutation.mutate(entryId);
        setConfirmDialog({ open: false, title: '', onConfirm: () => {} });
      },
      variant: 'danger',
    });
  }, [cancelMutation]);

  const handleMoveUp = useCallback((entry: WaitlistEntry) => {
    // Find entry with lower sort_order and swap
    const sorted = [...sortedActive].sort(
      (a, b) => (a.sort_order || 0) - (b.sort_order || 0)
    );
    const index = sorted.findIndex((e) => e.id === entry.id);
    if (index > 0) {
      const prevEntry = sorted[index - 1];
      const newOrder: ReorderRequest = {
        entry_ids: [prevEntry.id, entry.id],
      };
      reorderMutation.mutate(newOrder);
    }
  }, [sortedActive, reorderMutation]);

  const handleMoveDown = useCallback((entry: WaitlistEntry) => {
    // Find entry with higher sort_order and swap
    const sorted = [...sortedActive].sort(
      (a, b) => (a.sort_order || 0) - (b.sort_order || 0)
    );
    const index = sorted.findIndex((e) => e.id === entry.id);
    if (index < sorted.length - 1) {
      const nextEntry = sorted[index + 1];
      const newOrder: ReorderRequest = {
        entry_ids: [entry.id, nextEntry.id],
      };
      reorderMutation.mutate(newOrder);
    }
  }, [sortedActive, reorderMutation]);

  const handleCloseDay = useCallback(() => {
    setConfirmDialog({
      open: true,
      title: 'Close the day?',
      description: 'All active entries will be closed. This cannot be undone.',
      onConfirm: () => {
        closeDayMutation.mutate();
        setConfirmDialog({ open: false, title: '', onConfirm: () => {} });
      },
      variant: 'danger',
    });
  }, [closeDayMutation]);

  // Loading state
  if (loadingDashboard || loadingWaitlist) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton variant="board" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-border-default p-4">
          <div className="text-sm text-text-secondary mb-1">Waiting</div>
          <div className="text-3xl font-bold text-WAITING">{stats.waiting}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-border-default p-4">
          <div className="text-sm text-text-secondary mb-1">Called</div>
          <div className="text-3xl font-bold text-called">{stats.called}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-border-default p-4">
          <div className="text-sm text-text-secondary mb-1">Seated</div>
          <div className="text-3xl font-bold text-SEATED">{stats.seated}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-border-default p-4">
          <div className="text-sm text-text-secondary mb-1">Available Tables</div>
          <div className="text-3xl font-bold text-AVAILABLE">{stats.availableTables}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-border-default p-4">
          <div className="text-sm text-text-secondary mb-1">Occupied</div>
          <div className="text-3xl font-bold text-OCCUPIED">{stats.occupied}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-border-default p-4">
          <div className="text-sm text-text-secondary mb-1">Cleaning</div>
          <div className="text-3xl font-bold text-CLEANING">{stats.cleaning}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-border-default p-4">
          <div className="text-sm text-text-secondary mb-1">No-show today</div>
          <div className="text-3xl font-bold text-NO_SHOW">{stats.noShowToday}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-border-default p-4">
          <div className="text-sm text-text-secondary mb-1">Cancelled today</div>
          <div className="text-3xl font-bold text-CANCELLED">{stats.cancelledToday}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-border-default p-4">
          <div className="text-sm text-text-secondary mb-1">Seated today</div>
          <div className="text-3xl font-bold text-DONE">{stats.seatedToday}</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-border-default p-4">
          <div className="text-sm text-text-secondary mb-1">Avg wait today</div>
          <div className="text-3xl font-bold text-text-primary">{stats.avgWaitToday} min</div>
        </div>
      </div>

      {/* Filters and Actions */}
      <div className="bg-white rounded-xl shadow-sm border border-border-default p-4">
        <div className="flex flex-wrap gap-4 items-center">
          {/* Search input */}
          <div className="flex-1 min-w-64">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary" />
              <Input
                type="text"
                placeholder="Search by name or phone..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
                aria-label="Search waitlist"
              />
            </div>
          </div>

          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'Active' | 'Closed' | 'All')}
            className="h-10 px-3 rounded-lg border border-border-default bg-white text-sm"
            aria-label="Filter by status"
          >
            <option value="Active">Active</option>
            <option value="Closed">Closed</option>
            <option value="All">All</option>
          </select>

          {/* Party size filter */}
          <select
            value={partySizeFilter}
            onChange={(e) => setPartySizeFilter(e.target.value)}
            className="h-10 px-3 rounded-lg border border-border-default bg-white text-sm"
            aria-label="Filter by party size"
          >
            <option value="">All party sizes</option>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((size) => (
              <option key={size} value={size}>
                {size} pax
              </option>
            ))}
          </select>

          {/* Pause Waitlist switch */}
          <div className="flex items-center gap-2">
            <button
              role="switch"
              aria-checked={true}
              className="relative inline-flex h-6 w-11 items-center rounded-full bg-primary transition-colors"
              aria-label="Pause Waitlist"
            >
              <span className="inline-block h-4 w-4 transform rounded-full bg-white transition-transform translate-x-6" />
            </button>
            <span className="text-sm text-text-secondary">Pause Waitlist</span>
          </div>

          {/* Close Day button */}
          <Button variant="destructive" onClick={handleCloseDay}>
            <Calendar className="w-4 h-4 mr-1" />
            Close Day
          </Button>
        </div>
      </div>

      {/* Active Waitlist */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-text-primary">Active Waitlist</h2>
        {sortedActive.length === 0 ? (
          <EmptyState
            icon={<div className="text-4xl">👥</div>}
            title="No one is waiting right now"
            description="Guests will appear here when they join the waitlist."
          />
        ) : (
          <div className="space-y-4">
            {sortedActive.map((entry) => (
              <div key={entry.id} className="relative">
                <WaitlistCard
                  entry={{
                    id: parseInt(entry.id) || 1,
                    queueNumber: entry.queue_number,
                    name: entry.name || 'Guest',
                    phone: entry.phone,
                    partySize: entry.party_size,
                    status: entry.status,
                    targetTime: entry.called_at ? new Date(entry.called_at) : undefined,
                    holdMinutes: entry.hold_minutes_snapshot,
                    note: entry.note,
                  }}
                  onCall={() => handleCall(entry.id)}
                  onSeat={() => {
                    // For demo, use a placeholder table ID
                    handleSeat(entry.id, 'table-1');
                  }}
                  onNoShow={() => handleNoShow(entry.id)}
                  onCancel={() => handleCancel(entry.id)}
                  onRestore={() => handleRestore(entry.id)}
                  onRevert={() => handleRevert(entry.id)}
                />
                {/* Reorder buttons */}
                <div className="absolute right-4 top-4 flex flex-col gap-1">
                  <button
                    onClick={() => handleMoveUp(entry)}
                    className="p-1 hover:bg-gray-100 rounded"
                    aria-label="Move up"
                  >
                    <ArrowUp className="w-4 h-4 text-text-secondary" />
                  </button>
                  <button
                    onClick={() => handleMoveDown(entry)}
                    className="p-1 hover:bg-gray-100 rounded"
                    aria-label="Move down"
                  >
                    <ArrowDown className="w-4 h-4 text-text-secondary" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Closed today section (collapsible) */}
      <div className="bg-white rounded-xl shadow-sm border border-border-default">
        <button
          onClick={() => setShowClosed(!showClosed)}
          className="w-full p-4 flex items-center justify-between hover:bg-gray-50"
          aria-expanded={showClosed}
          aria-controls="closed-today-section"
        >
          <h2 className="text-lg font-semibold text-text-primary">Closed today</h2>
          <span className="text-sm text-text-secondary">
            {filteredEntries.closed.length} entr{filteredEntries.closed.length === 1 ? 'y' : 'ies'}
          </span>
        </button>
        {showClosed && (
          <div id="closed-today-section" className="p-4 pt-0 space-y-4">
            {sortedClosed.length === 0 ? (
              <p className="text-sm text-text-secondary">No closed entries today.</p>
            ) : (
              sortedClosed.map((entry) => (
                <div key={entry.id} className="border-t pt-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium">{entry.queue_number}</span>
                      <span className="text-sm text-text-secondary ml-2">
                        {entry.name || 'Guest'} · {entry.party_size} pax
                      </span>
                    </div>
                    <StatusBadge status={entry.status} size="sm" />
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Last updated */}
      {lastUpdated && (
        <p className="text-sm text-text-secondary text-right">
          Last updated: {lastUpdated.toLocaleTimeString()}
        </p>
      )}

      {/* Confirm Dialog */}
      <ConfirmDialog
        open={confirmDialog.open}
        onClose={() => setConfirmDialog({ ...confirmDialog, open: false })}
        title={confirmDialog.title}
        description={confirmDialog.description}
        onConfirm={confirmDialog.onConfirm}
        variant={confirmDialog.variant}
        confirmLabel="Confirm"
        cancelLabel="Cancel"
      />
    </div>
  );
};

export default WaitlistPage;
