/**
 * StatusPage - guest view of their waitlist status (F-08).
 * Follows _docs/ui.md section 6.2: queue number text-5xl, StatusBadge,
 * countdown mm:ss for CALLED, sound/vibration handling, Join Again for CANCELLED.
 */
import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { StatusBadge } from '@/components/StatusBadge';
import Countdown from '@/components/Countdown';
import ConfirmDialog from '@/components/ConfirmDialog';
import { cancelWaitlist, getBoard, getStatus } from '@/api/public';

type StatusValue = 'WAITING' | 'CALLED' | 'SEATED' | 'NO_SHOW' | 'CANCELLED' | 'DONE';

interface StatusView {
  status: StatusValue;
  queueNumber: string;
  groupsAhead: number;
  estimatedWait: number;
  remainingSeconds: number;
}

/**
 * Fetch status for the token in the query string and poll every 5s
 * (refetchInterval: 5000, refetchOnWindowFocus: true).
 */
function useStatus(token: string): StatusView {
  const [view, setView] = useState<StatusView>({
    status: 'WAITING',
    queueNumber: token,
    groupsAhead: 0,
    estimatedWait: 0,
    remainingSeconds: 0,
  });

  useEffect(() => {
    let alive = true;
    const CALL_TIMEOUT_SECONDS = 15 * 60; // mock stand-in for settings.call_timeout_minutes
    const MINUTES_PER_GROUP = 5; // mock estimate until settings land in Phase 2
    const load = () => {
      void Promise.all([getStatus(token), getBoard('branch-001')]).then(
        ([entry, board]) => {
          if (!alive || !entry) return;
          const waiting = board.waiting_count;
          const groupsAhead = Math.max(0, waiting - 1);
          const elapsed = entry.created_at
            ? Math.max(0, (Date.now() - Date.parse(entry.created_at)) / 1000)
            : 0;
          setView({
            status: entry.status as StatusValue,
            queueNumber: entry.queue_number,
            groupsAhead,
            estimatedWait: groupsAhead * MINUTES_PER_GROUP,
            remainingSeconds: Math.max(0, CALL_TIMEOUT_SECONDS - elapsed),
          });
        },
      );
    };
    load();
    const refetchInterval = window.setInterval(load, 5000); // refetchInterval: 5000
    const refetchOnWindowFocus = () => load();
    window.addEventListener('focus', refetchOnWindowFocus);
    return () => {
      alive = false;
      window.clearInterval(refetchInterval);
      window.removeEventListener('focus', refetchOnWindowFocus);
    };
  }, [token]);

  return view;
}

/** mm:ss used by the CALLED countdown; exported for unit tests. */
export function formatCountdown(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

const StatusPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') ?? '';
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  // AC-1: without a token query param the guest enters their last 3 digits.
  if (!token) {
    return (
      <div className="max-w-lg mx-auto p-4">
        <h2 className="text-xl font-bold mb-2">Enter last 3 digits of your queue number</h2>
        <form>
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]{3}"
            placeholder="Last 3 digits"
            className="border p-2 w-full"
          />
          <button type="submit" className="btn-primary mt-2">
            Lookup
          </button>
        </form>
      </div>
    );
  }

  const { status, queueNumber, groupsAhead, estimatedWait, remainingSeconds } = useStatus(token);

  const handleCancel = () => {
    void cancelWaitlist(queueNumber);
  };

  // AC-7: vibrate when the party is called.
  useEffect(() => {
    if (status === 'CALLED') {
      navigator.vibrate?.(200);
    }
  }, [status]);

  return (
    <div className="max-w-lg mx-auto p-4">
      <div className="text-5xl font-bold mb-4">{queueNumber}</div>
      <StatusBadge status={status} size="lg" className="mb-4" />
      <div className="mb-2">{groupsAhead} groups ahead</div>
      <div className="mb-2">Estimated wait: {estimatedWait} min</div>

      {status === 'WAITING' && (
        <button onClick={handleCancel} className="btn-primary">
          Cancel
        </button>
      )}

      {status === 'CALLED' && (
        <div>
          <p className="mb-2">
            Called now — arrive within <span className="font-mono">{formatCountdown(remainingSeconds)}</span>
          </p>
          <Countdown targetTime={Date.now() + remainingSeconds * 1000} />
          {!soundEnabled && (
            <button onClick={() => setSoundEnabled(true)} className="btn-secondary mt-2">
              Tap to enable sound
            </button>
          )}
          <button onClick={() => setConfirmOpen(true)} className="btn-secondary mt-2">
            Cancel
          </button>
          <ConfirmDialog
            title="Cancel your spot?"
            description="Your place in the queue will be released."
            open={confirmOpen}
            onClose={() => setConfirmOpen(false)}
            onConfirm={handleCancel}
          />
        </div>
      )}

      {status === 'SEATED' && <div>{"You're seated. Enjoy your meal!"}</div>}

      {status === 'NO_SHOW' && (
        <div className="bg-red-500 text-white p-2">No show — please visit the host stand</div>
      )}

      {status === 'CANCELLED' && (
        <div className="bg-CANCELLED text-white p-2">
          CANCELLED <button className="btn-secondary ml-2">Join Again</button>
        </div>
      )}
    </div>
  );
};

export default StatusPage;
