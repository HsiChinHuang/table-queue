/**
 * LookupPage - Guest lookup page for waitlist status.
 * F-09: Lookup page - normalize queue number, last-3 verify, navigate to status, 404 error state
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { EmptyState } from '@/components/EmptyState';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { getStatus } from '@/api/public';
import { ApiError } from '@/api/errors';

/**
 * Normalize queue number: trim whitespace and uppercase.
 * AC-2: Exported pure function for queue number normalization
 */
export function normalizeQueueNumber(input: string): string {
  return input.trim().toUpperCase();
}

/**
 * LookupPage component - allows guests to look up their waitlist status.
 * AC-1: File exists at frontend/src/pages/public/LookupPage.tsx
 */
const LookupPage: React.FC = () => {
  const navigate = useNavigate();
  const [queueNumber, setQueueNumber] = useState('');
  const [last3Phone, setLast3Phone] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const normalizedQueueNumber = normalizeQueueNumber(queueNumber);
    const statusToken = last3Phone.trim();

    // Validate inputs
    if (!normalizedQueueNumber) {
      setError('Please enter a queue number.');
      return;
    }

    if (statusToken.length !== 3 || !/^\d{3}$/.test(statusToken)) {
      setError('Please enter the last 3 digits of your phone number.');
      return;
    }

    setIsLoading(true);

    try {
      const result = await getStatus(normalizedQueueNumber);

      if (!result) {
        // AC-6: Failure message for not found
        setError('No matching waitlist entry found.');
        setIsLoading(false);
        return;
      }

      // AC-5: Success navigation to /status/{queueNumber}?token={statusToken}
      navigate(`/status/${normalizedQueueNumber}?token=${statusToken}`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 'WAITLIST_NOT_FOUND') {
          setError('No matching waitlist entry found.');
        } else {
          setError(err.message);
        }
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // AC-7: Mobile-first layout with max-w-md
  if (isLoading) {
    return (
      <div className="max-w-md mx-auto p-4">
        <LoadingSkeleton variant="form" />
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto p-4 space-y-4">
      <div className="text-center space-y-2">
        <h2 className="text-2xl font-bold">Check Your Status</h2>
        <p className="text-sm text-muted-foreground">
          Enter your queue number and the last 3 digits of your phone number.
        </p>
      </div>

      {error && (
        <EmptyState
          icon={<span className="text-4xl">⚠️</span>}
          title="Lookup Failed"
          description={error}
        />
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <Label htmlFor="queueNumber">Queue Number</Label>
          <Input
            id="queueNumber"
            type="text"
            placeholder="A001"
            value={queueNumber}
            onChange={(e) => setQueueNumber(e.target.value.toUpperCase())}
            maxLength={10}
            autoComplete="off"
          />
        </div>

        <div>
          <Label htmlFor="last3Phone">Last 3 Digits of Phone</Label>
          {/* AC-3: inputMode="numeric" and maxLength=3 */}
          <Input
            id="last3Phone"
            type="text"
            inputMode="numeric"
            maxLength={3}
            placeholder="123"
            value={last3Phone}
            onChange={(e) => setLast3Phone(e.target.value)}
            autoComplete="off"
          />
        </div>

        <Button type="submit" className="w-full">
          {/* AC-4: Submit button label */}
          Look Up Status
        </Button>
      </form>
    </div>
  );
};

export default LookupPage;
