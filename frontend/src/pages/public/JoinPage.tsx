// AC-13: Duplicate phone handling - shows message with View Status button linking to /lookup
import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Users, Clock, AlertCircle } from 'lucide-react';

import { usePublicBranch } from '@/api/hooks';
import { joinWaitlist, JoinWaitlistRequest } from '@/api/public';
import { ApiError } from '@/api/errors';
import { ROUTES } from '@/routes';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { EmptyState } from '@/components/EmptyState';

// Validation schema for join form
const joinFormSchema = z.object({
  name: z.string().min(1, 'Name is required').max(50, 'Name must be 50 characters or less'),
  phone: z
    .string()
    .min(1, 'Phone number is required')
    .refine(
      (phone) => {
        // Taiwan mobile: 09xx-xxx-xxx or 09xxxxxxxx (with optional dashes)
        // Taiwan landline: 02-xxxx-xxxx or 02xxxxxxxx (with optional dashes)
        const mobileRegex = /^09\d{2}-?\d{3}-?\d{3}$/;
        const landlineRegex = /^02-?\d{4}-?\d{4}$/;
        return mobileRegex.test(phone) || landlineRegex.test(phone);
      },
      { message: 'Please enter a valid Taiwan phone number (mobile: 09xx-xxx-xxx or landline: 02-xxxx-xxxx)' }
    ),
  partySize: z
    .number()
    .int()
    .min(1, 'Party size must be at least 1')
    .max(20, 'Party size must be 20 or less'),
  note: z.string().max(200, 'Note must be 200 characters or less').optional(),
});

export type JoinFormData = z.infer<typeof joinFormSchema>;

/**
 * Pure validation function exported for unit testing.
 * Validates join form data according to AC-8 through AC-11.
 * 
 * @param data - The form data to validate
 * @returns Object with isValid flag and errors object
 */
export function validateJoinForm(data: {
  name: string;
  phone: string;
  partySize: number | string;
  note?: string;
}): { isValid: boolean; errors: Record<string, string> } {
  const errors: Record<string, string> = {};

  // Name validation: 1-50 characters
  if (!data.name || data.name.trim().length === 0) {
    errors.name = 'Name is required';
  } else if (data.name.length > 50) {
    errors.name = 'Name must be 50 characters or less';
  }

  // Phone validation: Taiwan mobile 09xx-xxx-xxx or landline 02-xxxx-xxxx
  const mobileRegex = /^09\d{2}-?\d{3}-?\d{3}$/;
  const landlineRegex = /^02-?\d{4}-?\d{4}$/;
  if (!data.phone || data.phone.trim().length === 0) {
    errors.phone = 'Phone number is required';
  } else if (!mobileRegex.test(data.phone) && !landlineRegex.test(data.phone)) {
    errors.phone = 'Please enter a valid Taiwan phone number (mobile: 09xx-xxx-xxx or landline: 02-xxxx-xxxx)';
  }

  // Party size validation: 1-20
  const partySize = typeof data.partySize === 'string' ? parseInt(data.partySize, 10) : data.partySize;
  if (isNaN(partySize) || partySize < 1) {
    errors.partySize = 'Party size must be at least 1';
  } else if (partySize > 20) {
    errors.partySize = 'Party size must be 20 or less';
  }

  // Note validation: 0-200 characters
  if (data.note && data.note.length > 200) {
    errors.note = 'Note must be 200 characters or less';
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}

/**
 * JoinPage component - allows guests to join the restaurant waitlist.
 * 
 * Features:
 * - Displays restaurant/branch information from usePublicBranch hook
 * - Form with name, phone, partySize, and note fields
 * - Validation using react-hook-form with zod
 * - Error handling for WAITLIST_CLOSED, WAITLIST_DUPLICATE_PHONE, BRANCH_NOT_FOUND
 * - Success navigation to /status/{queueNumber}
 */
const JoinPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  
  // Get branch ID from query param or fallback to VITE_BRANCH_ID env var
  const searchParams = new URLSearchParams(window.location.search);
  const branchFromParam = searchParams.get('branch');
  const branchId = branchFromParam || import.meta.env.VITE_BRANCH_ID || '1';

  const { data: branch, isLoading, error } = usePublicBranch(branchId);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<JoinFormData>({
    resolver: zodResolver(joinFormSchema),
    defaultValues: {
      name: '',
      phone: '',
      partySize: 2,
      note: '',
    },
  });

  const onSubmit = async (data: JoinFormData) => {
    try {
      const request: JoinWaitlistRequest = {
        phone: data.phone,
        party_size: data.partySize,
        name: data.name,
      };

      const result = await joinWaitlist(request);
      
      // Clear form
      queryClient.invalidateQueries({ queryKey: ['publicBranch'] });

      // Navigate to status page with queue number
      if (result && result.queue_number) {
        navigate(`${ROUTES.STATUS.replace(':queueNumber', result.queue_number)}?token=${result.id}`);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        // Error handling is done via inline errors or toast
        throw err; // Let react-hook-form handle it
      }
      throw err;
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-bg-guest flex items-center justify-center p-4">
        <LoadingSkeleton variant="form" />
      </div>
    );
  }

  // Branch not found error
  if (error && (error as ApiError).code === 'BRANCH_NOT_FOUND') {
    return (
      <div className="min-h-screen bg-bg-guest flex items-center justify-center p-4">
        <EmptyState
          icon={<AlertCircle className="w-12 h-12 text-error" />}
          title="Branch Not Found"
          description="This branch is not available."
          action={
            <Button onClick={() => navigate(ROUTES.JOIN)}>
              Try Another Branch
            </Button>
          }
        />
      </div>
    );
  }

  // Branch data error (generic)
  if (error) {
    return (
      <div className="min-h-screen bg-bg-guest flex items-center justify-center p-4">
        <EmptyState
          icon={<AlertCircle className="w-12 h-12 text-error" />}
          title="Unable to Load"
          description="We couldn't load the restaurant information. Please try again later."
          action={
            <Button onClick={() => window.location.reload()}>
              Reload Page
            </Button>
          }
        />
      </div>
    );
  }

  // Waitlist closed - show message and hide form
  if (branch && !branch.is_waitlist_open) {
    return (
      <div className="min-h-screen bg-bg-guest flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-sm p-6 text-center">
          <AlertCircle className="w-12 h-12 text-warning mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-text-primary mb-2">
            {branch.restaurant_name}
          </h1>
          <p className="text-text-secondary mb-4">{branch.branch_name}</p>
          <div className="bg-warning/10 rounded-lg p-4 mb-6">
            <p className="text-warning font-medium">
              Waitlist is currently closed.
            </p>
            <p className="text-sm text-text-secondary mt-1">
              Please check back later.
            </p>
          </div>
          <Button variant="outline" onClick={() => navigate(ROUTES.LOOKUP)}>
            Check Status
          </Button>
        </div>
      </div>
    );
  }

  // Main join form
  return (
    <div className="min-h-screen bg-bg-guest flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        {/* Restaurant Info Header */}
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-text-primary mb-1">
            {branch?.restaurant_name}
          </h1>
          <p className="text-text-secondary mb-2">{branch?.branch_name}</p>
          
          {/* Hours display */}
          {branch?.hours && (
            <div className="flex items-center justify-center text-sm text-text-secondary mb-2">
              <Clock className="w-4 h-4 mr-1" />
              <span>{branch.hours}</span>
            </div>
          )}
          
          {/* Waiting count */}
          {branch?.waiting_count !== undefined && branch.waiting_count !== null && (
            <div className="flex items-center justify-center text-sm text-text-secondary">
              <Users className="w-4 h-4 mr-1" />
              <span>{branch.waiting_count} group(s) waiting</span>
            </div>
          )}
        </div>

        {/* Join Form Card */}
        <div className="bg-white rounded-2xl shadow-sm p-6">
          <h2 className="text-xl font-semibold text-text-primary mb-4">
            Join the Waitlist
          </h2>
          
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Name field */}
            <div>
              <Label htmlFor="name" className="block text-sm font-medium text-text-primary mb-1">
                Name <span className="text-error">*</span>
              </Label>
              <Input
                id="name"
                type="text"
                placeholder="Your name"
                error={errors.name?.message}
                {...register('name')}
                disabled={isSubmitting}
              />
            </div>

            {/* Phone field */}
            <div>
              <Label htmlFor="phone" className="block text-sm font-medium text-text-primary mb-1">
                Phone <span className="text-error">*</span>
              </Label>
              <Input
                id="phone"
                type="tel"
                placeholder="09xx-xxx-xxx or 02-xxxx-xxxx"
                error={errors.phone?.message}
                {...register('phone')}
                disabled={isSubmitting}
              />
            </div>

            {/* Party size field */}
            <div>
              <Label htmlFor="partySize" className="block text-sm font-medium text-text-primary mb-1">
                Party Size <span className="text-error">*</span>
              </Label>
              <Input
                id="partySize"
                type="number"
                min={1}
                max={20}
                error={errors.partySize?.message}
                {...register('partySize', { valueAsNumber: true })}
                disabled={isSubmitting}
              />
            </div>

            {/* Note field (optional) */}
            <div>
              <Label htmlFor="note" className="block text-sm font-medium text-text-primary mb-1">
                Note (optional)
              </Label>
              <Input
                id="note"
                type="text"
                placeholder="Any special requests..."
                error={errors.note?.message}
                {...register('note')}
                disabled={isSubmitting}
              />
            </div>

            {/* Submit button */}
            <Button
              type="submit"
              className="w-full h-12"
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Joining...' : 'Join Waitlist'}
            </Button>
          </form>

          {/* Duplicate phone error message */}
          {errors.phone?.message?.includes('already on the waitlist') && (
            <div className="mt-4 p-3 bg-warning/10 rounded-lg">
              <p className="text-warning text-sm">
                This phone number is already on the waitlist.
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                onClick={() => navigate(ROUTES.LOOKUP)}
              >
                View Status
              </Button>
            </div>
          )}
        </div>

        {/* Already waiting link */}
        <p className="text-center text-sm text-text-secondary mt-4">
          Already waiting?{' '}
          <button
            type="button"
            className="text-primary hover:underline"
            onClick={() => navigate(ROUTES.LOOKUP)}
          >
            Check your status
          </button>
        </p>
      </div>
    </div>
  );
};

export default JoinPage;
