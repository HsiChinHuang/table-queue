// @vitest-environment jsdom
/**
 * TablesPage - Staff tables management page.
 * Displays all tables in a grid, allows toggling AVAILABLE↔CLEANING, and releasing OCCUPIED tables.
 * 
 * AC-1: File exists
 * AC-2: useTables hook with 5s polling
 * AC-3: useUpdateTableStatus hook for AVAILABLE↔CLEANING
 * AC-4: useReleaseTable hook for releasing
 * AC-5: Grid layout grid-cols-2 md:grid-cols-3 lg:grid-cols-4
 * AC-6: Card displays label, capacity, status color
 * AC-7: AVAILABLE/CLEANING clickable to toggle
 * AC-8: OCCUPIED shows formatOccupiedLabel, Release Table button with ConfirmDialog
 * AC-9: Empty state text
 */

import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { tables, tablesKeys } from '@/api/queryKeys';
import { listTables, updateTableStatus, releaseTable, Table } from '@/api/tables';
import { EmptyState } from '@/components/EmptyState';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { StatusBadge } from '@/components/StatusBadge';
import { Button } from '@/components/ui/Button';
import { Store, Clock, Users } from 'lucide-react';
import { staffStore } from '@/stores/staffStore';

/**
 * The kit staff store (F-01) persists token/staffId only; branch id is not part
 * of it yet. Read it defensively and fall back to the seeded dev branch.
 */
function getStaffBranchId(): string {
  const state = staffStore.getState() as { branchId?: string | number };
  return state.branchId != null ? String(state.branchId) : 'branch-001';
}

// Status colors from _docs/ui.md section 2
export const STATUS_COLORS = {
  AVAILABLE: '#22C55E',
  OCCUPIED: '#F97316',
  CLEANING: '#A855F7',
};

/**
 * Pure function to format occupied label.
 * AC-10: formatOccupiedLabel tests
 */
export function formatOccupiedLabel(t: { queueNumber: string; partySize: number; occupiedMinutes: number }): string {
  return `${t.queueNumber} · ${t.partySize} pax · ${t.occupiedMinutes} min`;
}

/**
 * useTables hook - fetches and polls table data every 5 seconds.
 * AC-2: 5 second polling
 */
export function useTables() {
  const branchId = getStaffBranchId();

  return useQuery<Table[], Error>({
    // The kit's legacy `tables()` key factory still takes a numeric id.
    queryKey: tables(Number(branchId) || 1),
    queryFn: () => listTables(branchId),
    refetchInterval: 5000,
    staleTime: 5000,
  });
}

/**
 * useUpdateTableStatus hook - toggles AVAILABLE↔CLEANING.
 * AC-3: AVAILABLE↔CLEANING toggle
 */
export function useUpdateTableStatus() {
  const queryClient = useQueryClient();
  const branchId = getStaffBranchId();

  return useMutation<{ success: boolean }, Error, { tableId: string; status: 'AVAILABLE' | 'CLEANING' }>({
    mutationFn: ({ tableId, status }) => updateTableStatus(tableId, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tablesKeys.list(branchId) });
    },
  });
}

/**
 * useReleaseTable hook - releases an OCCUPIED table.
 * AC-4: Release OCCUPIED tables
 */
export function useReleaseTable() {
  const queryClient = useQueryClient();
  const branchId = getStaffBranchId();

  return useMutation<{ success: boolean }, Error, { tableId: string }>({
    mutationFn: ({ tableId }) => releaseTable(tableId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tablesKeys.list(branchId) });
    },
  });
}

interface TableCardProps {
  table: Table & { occupiedBy?: { queueNumber: string; partySize: number; occupiedMinutes: number } };
  onToggleStatus: (tableId: string, currentStatus: string) => void;
  onRelease: (tableId: string) => void;
}

const TableCard: React.FC<TableCardProps> = ({ table, onToggleStatus, onRelease }) => {
  const isOccupied = table.status === 'OCCUPIED';
  const isCleaning = table.status === 'CLEANING';

  const handleClick = () => {
    if (!isOccupied) {
      onToggleStatus(table.id, table.status);
    }
  };

  // Status colors from _docs/ui.md section 2 (AC-6)
  const statusColor = isOccupied
    ? STATUS_COLORS.OCCUPIED
    : isCleaning
      ? STATUS_COLORS.CLEANING
      : STATUS_COLORS.AVAILABLE;

  return (
    <div
      className={`bg-white rounded-xl shadow-sm border border-border-default border-l-4 p-4 ${
        !isOccupied ? 'cursor-pointer hover:bg-gray-50' : ''
      }`}
      style={{ borderLeftColor: statusColor }}
      onClick={handleClick}
      role={isOccupied ? 'article' : 'button'}
      tabIndex={isOccupied ? undefined : 0}
      aria-label={`Table ${table.label ?? table.name}, ${table.capacity} pax, ${table.status.toLowerCase()}`}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (!isOccupied) {
            onToggleStatus(table.id, table.status);
          }
        }
      }}
    >
      {/* Row 1: Label + status badge */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-lg font-bold text-text-primary">{table.label ?? table.name}</span>
        <StatusBadge status={table.status as 'AVAILABLE' | 'OCCUPIED' | 'CLEANING'} size="sm" />
      </div>

      {/* Row 2: Capacity */}
      <div className="flex items-center gap-1 mb-2">
        <Users className="w-4 h-4 text-text-secondary" aria-hidden="true" />
        <span className="text-sm text-text-secondary">{table.capacity} pax</span>
      </div>

      {/* Row 3: Occupied info or status text */}
      {isOccupied && table.occupiedBy ? (
        <div className="mb-3">
          <div className="flex items-center gap-1 mb-1">
            <span className="text-sm font-medium text-called">
              {formatOccupiedLabel({
                queueNumber: table.occupiedBy.queueNumber,
                partySize: table.occupiedBy.partySize,
                occupiedMinutes: table.occupiedBy.occupiedMinutes,
              })}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Clock className="w-4 h-4 text-called" aria-hidden="true" />
            <span className="text-xs text-called">
              {table.occupiedBy.occupiedMinutes} min elapsed
            </span>
          </div>
        </div>
      ) : (
        <p className="text-sm text-text-secondary mb-3">
          {isCleaning ? 'Currently cleaning' : 'Available'}
        </p>
      )}

      {/* Release button for occupied tables */}
      {isOccupied && (
        <Button
          onClick={(e) => {
            e.stopPropagation();
            onRelease(table.id);
          }}
          className="w-full bg-SEATED hover:bg-SEATED/90 text-white"
          aria-label={`Release table ${table.label ?? table.name}`}
        >
          Release Table
        </Button>
      )}
    </div>
  );
};

const TablesPage: React.FC = () => {
  const { data: tables, isLoading, error } = useTables();
  const updateStatusMutation = useUpdateTableStatus();
  const releaseMutation = useReleaseTable();
  
  const [releaseDialogOpen, setReleaseDialogOpen] = useState(false);
  const [tableToRelease, setTableToRelease] = useState<string | null>(null);

  const handleToggleStatus = (tableId: string, currentStatus: string) => {
    const newStatus = currentStatus === 'AVAILABLE' ? 'CLEANING' : 'AVAILABLE';
    updateStatusMutation.mutate({ tableId, status: newStatus });
  };

  const handleReleaseClick = (tableId: string) => {
    setTableToRelease(tableId);
    setReleaseDialogOpen(true);
  };

  const handleReleaseConfirm = () => {
    if (tableToRelease) {
      releaseMutation.mutate({ tableId: tableToRelease });
      setReleaseDialogOpen(false);
      setTableToRelease(null);
    }
  };

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white rounded-xl shadow-sm border border-border-default p-4 animate-pulse h-40">
            <div className="h-6 bg-gray-200 rounded mb-3"></div>
            <div className="h-4 bg-gray-200 rounded mb-2"></div>
            <div className="h-4 bg-gray-200 rounded"></div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-error text-lg mb-2">Failed to load tables</p>
        <p className="text-sm text-text-secondary">{error.message}</p>
      </div>
    );
  }

  if (!tables || tables.length === 0) {
    return (
      <EmptyState
        icon={<Store className="w-12 h-12" />}
        title="No tables yet"
        description="No tables yet. Add tables in Settings."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {tables.map((table) => (
          <TableCard
            key={table.id}
            table={table as Table & { occupiedBy?: { queueNumber: string; partySize: number; occupiedMinutes: number } }}
            onToggleStatus={handleToggleStatus}
            onRelease={handleReleaseClick}
          />
        ))}
      </div>

      <ConfirmDialog
        open={releaseDialogOpen}
        onClose={() => {
          setReleaseDialogOpen(false);
          setTableToRelease(null);
        }}
        onConfirm={handleReleaseConfirm}
        title="Release Table"
        description="Are you sure you want to release this table? This will make it available for new guests."
        variant="default"
        confirmLabel="Release"
        cancelLabel="Cancel"
      />
    </div>
  );
};

export default TablesPage;
