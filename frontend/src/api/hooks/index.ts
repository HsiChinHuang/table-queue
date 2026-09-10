// API hooks for TanStack Query

import { useQuery } from '@tanstack/react-query';
import { getPublicBranch, PublicBranch } from '../public';
import { publicBranchKeys } from '../queryKeys';

/**
 * Hook to fetch public branch information.
 * Used by JoinPage and BoardPage to display restaurant/branch info.
 */
export function usePublicBranch(branchId: string) {
  return useQuery<PublicBranch, Error>({
    queryKey: publicBranchKeys.get(branchId),
    queryFn: () => getPublicBranch(branchId),
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 2,
  });
}
