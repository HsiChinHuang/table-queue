/**
 * Staff Login Page - PIN authentication with remember-me support.
 * F-11: LoginPage
 */

import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { staffStore } from '@/stores/staffStore';
import { login } from '@/api/auth';
import { isApiError } from '@/api/errors';
import { ROUTES } from '@/routes';

export const STAFF_TOKEN_KEY = 'tq_staff_token';

// Storage selection helper: remember-me decides where the raw token lives
export function tokenStorageFor(remember: boolean): 'localStorage' | 'sessionStorage' {
  return remember ? 'localStorage' : 'sessionStorage';
}

const loginSchema = z.object({
  pin: z.string().min(1, 'PIN is required'),
  remember: z.boolean().default(true),
});

type LoginForm = z.infer<typeof loginSchema>;

function NavigateToWaitlist() {
  const navigate = useNavigate();
  React.useEffect(() => {
    navigate(ROUTES.STAFF_WAITLIST, { replace: true });
  }, [navigate]);
  return null;
}

function LoginPage() {
  const navigate = useNavigate();
  const token = staffStore((s) => s.token);
  const setToken = staffStore((s) => s.setToken);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { pin: '', remember: true },
  });

  // Redirect guard: already-authenticated staff skip the login screen
  if (token) {
    return <NavigateToWaitlist />;
  }

  const onSubmit = async (data: LoginForm) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await login({ pin: data.pin });
      window[tokenStorageFor(data.remember)].setItem(STAFF_TOKEN_KEY, response.token);
      setToken(response.token);
      // Route constant ROUTES.STAFF_WAITLIST === '/staff/waitlist'
      navigate('/staff/waitlist', { replace: true });
    } catch (err) {
      const code = isApiError(err)
        ? err.code
        : err && typeof err === 'object' && 'code' in err
          ? String((err as { code: unknown }).code)
          : 'INTERNAL_ERROR';
      if (code === 'AUTH_INVALID_PIN') {
        setError('Invalid PIN.');
      } else if (code === 'AUTH_RATE_LIMITED') {
        setError('Too many attempts. Please try again later.');
      } else {
        setError('An unexpected error occurred.');
      }
      setIsLoading(false);
    }
  };

  const busy = isLoading || isSubmitting;

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F8FAFC] px-4">
      <div className="w-full max-w-sm">
        <div className="rounded-2xl bg-white p-8 shadow-lg">
          <h1 className="mb-6 text-center text-2xl font-bold text-primary">Staff Login</h1>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="pin">PIN</Label>
              <Input
                id="pin"
                type="password" inputMode="numeric"
                placeholder="Enter your PIN"
                autoComplete="current-password"
                disabled={busy}
                aria-invalid={errors.pin ? true : undefined}
                {...register('pin')}
              />
              {errors.pin && (
                <p id="pin-error" className="text-sm text-error">
                  {errors.pin.message}
                </p>
              )}
            </div>

            <div className="flex items-center">
              <input
                id="remember"
                type="checkbox" defaultChecked
                disabled={busy}
                {...register('remember')}
                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <Label htmlFor="remember" className="ml-2 text-sm">
                Remember me
              </Label>
            </div>

            {error && (
              <p className="text-sm text-error" role="alert">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full h-12" disabled={busy}>
              Login
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
