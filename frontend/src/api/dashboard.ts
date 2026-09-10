import { get } from './client';

export interface DashboardResponse {
  branch_id: string;
  total_tables: number;
  available_tables: number;
  occupied_tables: number;
  waiting_count: number;
  called_count: number;
}

// AC-6: getDashboard endpoint
export async function getDashboard(_branchId: string): Promise<DashboardResponse> {
  const result = await get<DashboardResponse>('/staff/dashboard');
  return result!;
}
