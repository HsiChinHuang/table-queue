import { QueryKey } from '@tanstack/react-query';

// Query key factories for TanStack Query
// AC-5: All 6 areas covered - board, status, waitlist, tables, settings, dashboard

export const waitlistKeys = {
  all: ['waitlist'] as const,
  list: (branchId: string) => [...waitlistKeys.all, 'list', branchId] as QueryKey,
  status: (branchId: string, queueNumber: string) =>
    [...waitlistKeys.all, 'status', branchId, queueNumber] as QueryKey,
};

export const tablesKeys = {
  all: ['tables'] as const,
  list: (branchId: string) => [...tablesKeys.all, 'list', branchId] as QueryKey,
  detail: (branchId: string, tableId: string) =>
    [...tablesKeys.all, 'detail', branchId, tableId] as QueryKey,
};

export const dashboardKeys = {
  all: ['dashboard'] as const,
  get: (branchId: string) => [...dashboardKeys.all, branchId] as QueryKey,
};

export const settingsKeys = {
  all: ['settings'] as const,
  get: (branchId: string) => [...settingsKeys.all, branchId] as QueryKey,
};

export const publicBranchKeys = {
  all: ['publicBranch'] as const,
  get: (branchId: string) => [...publicBranchKeys.all, branchId] as QueryKey,
};

export const boardKeys = {
  all: ['board'] as const,
  get: (branchId: string) => [...boardKeys.all, branchId] as QueryKey,
};

// F-04: named query-key functions per AGENTS.md section 8 (TanStack array format)
export const waitlist = (branchId: number) => ['waitlist', branchId];
export const waitlistStatus = (branchId: number, queueNumber: string) => ['waitlistStatus', branchId, queueNumber];
export const tables = (branchId: number) => ['tables', branchId];
export const dashboard = (branchId: number) => ['dashboard', branchId];
export const settings = (branchId: number) => ['settings', branchId];
export const publicBranch = (branchId: number) => ['publicBranch', branchId];
export const board = (branchId: number) => ['board', branchId];
