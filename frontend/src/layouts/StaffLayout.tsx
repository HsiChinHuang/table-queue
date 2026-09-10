import { Outlet, Navigate, Link, useLocation } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import { useStaffStore } from '@/api/staffStore';
import DevBadge from '@/components/DevBadge';
import { ROUTES } from '@/routes';

function StaffLayout() {
  const { token, clearToken } = useStaffStore();
  const location = useLocation();

  // Redirect to login if no token (except on login page itself)
  if (!token && location.pathname !== ROUTES.STAFF_LOGIN) {
    return <Navigate to={ROUTES.STAFF_LOGIN} replace />;
  }

  const handleLogout = () => {
    clearToken();
  };

  const navItems = [
    { label: 'Waitlist', path: ROUTES.STAFF_WAITLIST },
    { label: 'Tables', path: ROUTES.STAFF_TABLES },
    { label: 'Settings', path: ROUTES.ADMIN_SETTINGS },
  ];

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-primary">
      <header className="border-b bg-white">
        <div className="container mx-auto max-w-7xl px-4 py-3">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold">TableQueue Staff</h1>
            <nav className="flex items-center gap-4">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className="text-sm font-medium text-muted-foreground hover:text-primary"
                >
                  {item.label}
                </Link>
              ))}
              <button
                onClick={handleLogout}
                className="flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-primary"
                aria-label="Log out"
              >
                <LogOut className="h-4 w-4" />
                LogOut
              </button>
            </nav>
          </div>
        </div>
      </header>
      <main className="container mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
      <DevBadge />
    </div>
  );
}

export default StaffLayout;
