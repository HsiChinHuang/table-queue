import { Outlet } from 'react-router-dom';
import DevBadge from '@/components/DevBadge';

function PublicLayout() {
  return (
    <div className="min-h-screen bg-[#FFFBF5] text-primary">
      <header className="p-4">
        <h1 className="text-2xl font-bold">TableQueue</h1>
        <p className="text-sm text-muted-foreground">Restaurant Waitlist Manager</p>
      </header>
      <main className="container mx-auto max-w-md px-4 py-6">
        <Outlet />
      </main>
      <footer className="p-4 text-center text-sm text-muted-foreground">
        &copy; {new Date().getFullYear()} TableQueue
      </footer>
      <DevBadge />
    </div>
  );
}

export default PublicLayout;
