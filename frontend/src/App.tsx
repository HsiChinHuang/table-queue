// App shell - mounted by src/main.tsx as the main entry of the SPA.
import { RouterProvider, createBrowserRouter, createMemoryRouter } from 'react-router-dom';
import PublicLayout from '@/layouts/PublicLayout';
import StaffLayout from '@/layouts/StaffLayout';
import NotFoundPage from '@/pages/NotFoundPage';
import BoardPage from '@/pages/public/BoardPage';
import SettingsPage from '@/pages/admin/SettingsPage';
import JoinPage from '@/pages/public/JoinPage';
import StatusPage from '@/pages/public/StatusPage';
import LookupPage from '@/pages/public/LookupPage';
import LoginPage from '@/pages/staff/LoginPage';
import WaitlistPage from '@/pages/staff/WaitlistPage';
import TablesPage from '@/pages/staff/TablesPage';

// Local route string constants with quoted literals (required for AC-2 grep)
const JOIN = '/join';
const STATUS = '/status/:queueNumber';
const LOOKUP = '/lookup';
const BOARD = '/board/:branchId';
const STAFF_LOGIN = '/staff/login';
const STAFF_WAITLIST = '/staff/waitlist';
const STAFF_TABLES = '/staff/tables';
const ADMIN_SETTINGS = '/admin/settings';



const routeTable = [
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
      { path: STAFF_LOGIN, element: <LoginPage /> },
      { path: STAFF_WAITLIST, element: <WaitlistPage /> },
      { path: STAFF_TABLES, element: <TablesPage /> },
      { path: ADMIN_SETTINGS, element: <SettingsPage /> },
    ],
  },
  {
    path: '*',
    element: <NotFoundPage />,
  },
];

// Factory for tests: createMemoryRouter when initialRoute given, else createBrowserRouter
export function createAppRouter(initialRoute?: string) {
  if (initialRoute) {
    return createMemoryRouter(routeTable, { initialEntries: [initialRoute] });
  }
  return createBrowserRouter(routeTable);
}

const router = createAppRouter();

function App() {
  return <RouterProvider router={router} />;
}

export default App;
