import { post } from './client';

// AC-6: resetData endpoint
export async function resetData(_branchId: string): Promise<{ success: boolean }> {
  const result = await post<{ success: boolean }>('/admin/reset');
  return result!;
}
