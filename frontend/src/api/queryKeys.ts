export const waitlist = (branchId: number) => ['waitlist', branchId];
export const waitlistStatus = (branchId: number, queueNumber: string) => ['waitlistStatus', branchId, queueNumber];
export const tables = (branchId: number) => ['tables', branchId];
export const dashboard = (branchId: number) => ['dashboard', branchId];
export const settings = (branchId: number) => ['settings', branchId];
export const publicBranch = (branchId: number) => ['publicBranch', branchId];
export const board = (branchId: number) => ['board', branchId];
