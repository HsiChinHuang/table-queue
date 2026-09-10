// Route constants for TableQueue application
export const ROUTES = {
  // Public routes
  JOIN: '/join',
  STATUS: '/status/:queueNumber',
  LOOKUP: '/lookup',
  BOARD: '/board/:branchId',
  // Staff routes
  STAFF_LOGIN: '/staff/login',
  STAFF_WAITLIST: '/staff/waitlist',
  STAFF_TABLES: '/staff/tables',
  // Admin routes
  ADMIN_SETTINGS: '/admin/settings',
};

export default ROUTES;
