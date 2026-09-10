/**
 * LoginPage component - Staff authentication with PIN.
 * AC-1: PIN input type=password, inputMode=numeric
 * AC-2: Remember me checkbox with defaultChecked
 * AC-3: Login button with text "Login"
 * AC-4: Error message "Invalid PIN." for AUTH_INVALID_PIN
 * AC-5: On success, store token and navigate to /staff/waitlist
 * AC-6: Redirect guard for already-logged-in users
 * AC-7: tokenStorageFor pure function exported
 * AC-8: AUTH_RATE_LIMITED error handling
 * AC-9: Container uses max-w-sm class
 */
import React from 'react';
import { useForm } from 'react-hook-form';
import { useNavigate, Navigate } from 'react-router-dom';
import { useStaffStore } from '@/api/staffStore';
import { login } from '@/api/auth';
import { ApiError, getErrorMessage } from '@/api/errors';
import { ROUTES } from '@/routes';

// AC-7: Pure function for storage selection
export function tokenStorageFor(remember: boolean): 'localStorage' | 'sessionStorage' {
  return remember ? 'localStorage' : 'sessionStorage';
}

interface LoginForm {
  pin: string;
  remember: boolean;
}

function LoginPage(): React.ReactElement {
  const navigate = useNavigate();
  const { token, setToken } = useStaffStore();
  const isAuthenticated = !!token;
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);

  // AC-6: Redirect guard for already-logged-in users
  if (isAuthenticated) {
    return <Navigate to={ROUTES.STAFF_WAITLIST} replace />;
  }

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    defaultValues: {
      pin: '',
      remember: true,
    },
  });

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await login({ pin: data.pin });
      if (response?.token) {
        setToken(response.token);
        // AC-5: Navigate to /staff/waitlist on success
        navigate(ROUTES.STAFF_WAITLIST, { replace: true });
      }
    } catch (err) {
      if (err instanceof ApiError) {
        // AC-4: AUTH_INVALID_PIN error message
        if (err.code === 'AUTH_INVALID_PIN') {
          setError('Invalid PIN.');
        }
        // AC-8: AUTH_RATE_LIMITED error message
        else if (err.code === 'AUTH_RATE_LIMITED' || err.code === 'RATE_LIMITED') {
          setError('Too many attempts. Please try again later.');
        } else {
          setError(getErrorMessage(err.code));
        }
      } else {
        setError('Login failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-staff px-4">
      <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-sm border border-border-default">
        <h1 className="text-xl font-bold text-text-primary mb-6 text-center">Staff Login</h1>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* AC-1: PIN input with type=password and inputMode=numeric on same line */}
          <div>
            <label htmlFor="pin" className="block text-sm font-medium text-text-secondary mb-1">
              PIN
            </label>
            <input
              id="pin"
              type="password" inputMode="numeric"
              autoComplete="current-password"
              className="w-full px-3 py-2 border border-border-default rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              placeholder="Enter your PIN"
              disabled={isLoading}
              {...register('pin', { required: 'PIN is required' })}
            />
            {errors.pin && (
              <p className="mt-1 text-sm text-red-600">{errors.pin.message}</p>
            )}
          </div>

          {/* AC-2: Remember me checkbox with type=checkbox and defaultChecked on same line */}
          <div className="flex items-center">
            <input
              id="remember"
              type="checkbox" defaultChecked
              className="h-4 w-4 text-primary border-border-default rounded focus:ring-primary"
              disabled={isLoading}
              {...register('remember')}
            />
            <label htmlFor="remember" className="ml-2 text-sm text-text-secondary">
              Remember me
            </label>
          </div>

          {/* AC-3: Login button */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2 px-4 bg-primary hover:bg-primary-hover text-white font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default LoginPage;
