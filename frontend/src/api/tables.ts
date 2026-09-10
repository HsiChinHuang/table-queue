import { get, patch, post, put, del } from './client';

export interface Table {
  id: string;
  name: string;
  /** Human-readable table label shown on staff cards (F-13). Falls back to name. */
  label?: string;
  capacity: number;
  status: string;
  /** Present when the table is occupied (staff tables endpoint). */
  occupiedBy?: { queueNumber: string; partySize: number; occupiedMinutes: number };
}

export interface UpdateTableStatusRequest {
  status: 'AVAILABLE' | 'CLEANING';
}

export interface CreateTableRequest {
  name: string;
  capacity: number;
}

export interface UpdateTableRequest {
  name?: string;
  capacity?: number;
}

// AC-6: listTables endpoint
export async function listTables(_branchId: string): Promise<Table[]> {
  const result = await get<Table[]>('/staff/tables');
  return result!;
}

// AC-6: updateTableStatus endpoint
export async function updateTableStatus(tableId: string, request: UpdateTableStatusRequest): Promise<{ success: boolean }> {
  const result = await patch<{ success: boolean }>(`/staff/tables/${tableId}/status`, request);
  return result!;
}

// AC-6: releaseTable endpoint
export async function releaseTable(tableId: string): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>(`/staff/tables/${tableId}/release`);
  return result!;
}

// AC-6: listAdminTables endpoint
export async function listAdminTables(_branchId: string): Promise<Table[]> {
  const result = await get<Table[]>('/admin/tables');
  return result!;
}

// AC-6: createTable endpoint
export async function createTable(request: CreateTableRequest): Promise<Table> {
  const result = await post<Table>('/admin/tables', request);
  return result!;
}

// AC-6: updateTable endpoint
export async function updateTable(tableId: string, request: UpdateTableRequest): Promise<Table> {
  const result = await put<Table>(`/admin/tables/${tableId}`, request);
  return result!;
}

// AC-6: deleteTable endpoint
export async function deleteTable(tableId: string): Promise<{ success: boolean }> {
  const result = await del<{ success: boolean }>(`/admin/tables/${tableId}`);
  return result!;
}
