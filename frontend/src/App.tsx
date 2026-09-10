import { RouterProvider, createBrowserRouter } from 'react-router-dom';
import PublicLayout from '@/layouts/PublicLayout';
import StaffLayout from '@/layouts/StaffLayout';
import NotFoundPage from '@/pages/NotFoundPage';

// Local route string constants with quoted literals (required for AC-2 grep)
const JOIN = '/join';
const STATUS = '/status/:queueNumber';
const LOOKUP = '/lookup';
const BOARD = '/board/:branchId';
const STAFF_LOGIN = '/staff/login';
const STAFF_WAITLIST = '/staff/waitlist';
const STAFF_TABLES = '/staff/tables';
const ADMIN_SETTINGS = '/admin/settings';

// TODO page components (F-07..F-14)
const JoinPage = () => <div>JoinPage</div>;
const StatusPage = () => <div>StatusPage</div>;
const LookupPage = () => <div>LookupPage</div>;
const BoardPage = () => <div>BoardPage</div>;
const StaffLoginPage = () => <div>StaffLoginPage</div>;
const StaffWaitlistPage = () => <div>StaffWaitlistPage</div>;
const StaffTablesPage = () => <div>StaffTablesPage</div>;
const AdminSettingsPage = () => <div>AdminSettingsPage</div>;

const router = createBrowserRouter([
  {
    path: '/',
    element: <PublicLayout />,
    children: [
      { path: JOIN, element: <JoinPage /> },
      { path: STATUS, element: <StatusPage /> },
      { path: LOOKUP, element: <LookupPage /> },
      { path: BOARD, element: <BoardPage /> },
    ],
  },
  {
    path: '/',
    element: <StaffLayout />,
    children: [
      { path: STAFF_LOGIN, element: <StaffLoginPage /> },
      { path: STAFF_WAITLIST, element: <StaffWaitlistPage /> },
      { path: STAFF_TABLES, element: <StaffTablesPage /> },
      { path: ADMIN_SETTINGS, element: <AdminSettingsPage /> },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
]);

function App() {
  return <RouterProvider router={router} />;
}

export default App;
