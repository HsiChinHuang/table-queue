import { Link } from 'react-router-dom';
import { ROUTES } from '@/routes';

function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-bold">Page not found.</h1>
      <p className="text-muted-foreground">The page you are looking for does not exist.</p>
      <Link
        to={`${ROUTES.JOIN}?branch=1`}
        className="rounded-lg bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90"
      >
        Go home
      </Link>
    </div>
  );
}

export default NotFoundPage;
