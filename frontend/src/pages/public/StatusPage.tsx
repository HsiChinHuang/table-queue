/**
 * StatusPage - guest view of their waitlist status (F-08).
 * Follows _docs/ui.md section 6.2: queue number text-5xl, StatusBadge,
 * countdown mm:ss for CALLED, sound/vibration handling, Join Again for CANCELLED.
 *
 * Guest credential transport (T11 D-3): the minted status_token is held in this
 * module's memory, never in the URL. JoinPage writes it after a join; LookupPage
 * writes the read-only phone tail; this page reads it back. The query string
 * carries only the queue number, so the credential never reaches browser
 * history, an access log, or a Referer header.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { StatusBadge } from '@/components/StatusBadge';
import Countdown from '@/components/Countdown';
import ConfirmDialog from '@/components/ConfirmDialog';
import { cancelWaitlist, getBoard, getStatus, OwnershipFactor } from '@/api/public';

type StatusValue = 'WAITING' | 'CALLED' | 'SEATED' | 'NO_SHOW' | 'CANCELLED' | 'DONE';

interface StatusView {
  status: StatusValue;
  queueNumber: string;
  groupsAhead: number;
  estimatedWait: number;
  remainingSeconds: number;
}

// ---------------------------------------------------------------------------
// In-memory guest credential (T11 D-3)
// ---------------------------------------------------------------------------

export type GuestFactor = OwnershipFactor;

let guestFactor: GuestFactor | null = null;

export function setGuestFactor(factor: GuestFactor): void {
  guestFactor = factor;
}

export function getGuestFactor(): GuestFactor | null {
  return guestFactor;
}

export function clearGuestFactor(): void {
  guestFactor = null;
}

/**
 * Fetch status for the guest's in-memory credential and poll every 5s
 * (refetchInterval: 5000, refetchOnWindowFocus: true).
 */
function useStatus(queueNumber: string, factor: GuestFactor): StatusView {
  const [view, setView] = useState<StatusView>({
    status: 'WAITING',
    queueNumber: queueNumber,
    groupsAhead: 0,
    estimatedWait: 0,
    remainingSeconds: 0,
  });

  useEffect(() => {
    let alive = true;
    const CALL_TIMEOUT_SECONDS = 15 * 60; // mock stand-in for settings.call_timeout_minutes
    const MINUTES_PER_GROUP = 5; // mock estimate until settings land in Phase 2
    const branchId = Number(import.meta.env.VITE_BRANCH_ID || 1);
    const load = () => {
      void Promise.all([getStatus(queueNumber, factor), getBoard(branchId)]).then(
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
  }, [queueNumber, factor]);

  return view;
}

/** mm:ss used by the CALLED countdown; exported for unit tests. */
export function formatCountdown(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

const StatusView: React.FC<{ queueNumber: string; factor: GuestFactor }> = ({
  queueNumber,
  factor,
}) => {
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  // The minted token is the only factor that authorizes a cancel (T11 D-1); the
  // read-only phone tail shows the status but not the cancel control.
  const hasToken = 'token' in factor;

  const {
    status,
    queueNumber: displayedQueueNumber,
    groupsAhead,
    estimatedWait,
    remainingSeconds,
  } = useStatus(queueNumber, factor);

  const handleCancel = () => {
    void cancelWaitlist(queueNumber, factor);
  };

  // AC-7: vibrate when the party is called.
  useEffect(() => {
    if (status === 'CALLED') {
      navigator.vibrate?.(200);
    }
  }, [status]);

  return (
    <div className="max-w-lg mx-auto p-4">
      <div className="text-5xl font-bold mb-4">{displayedQueueNumber}</div>
      <StatusBadge status={status} size="lg" className="mb-4" />
      <div className="mb-2">{groupsAhead} groups ahead</div>
      <div className="mb-2">Estimated wait: {estimatedWait} min</div>

      {status === 'WAITING' && hasToken && (
        <button onClick={handleCancel} className="btn-primary">
          Cancel
        </button>
      )}

      {status === 'WAITING' && !hasToken && (
        <p className="text-sm text-muted-foreground mb-2">
          Cancellation needs the token you received when you joined.
        </p>
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
          {hasToken && (
            <>
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
            </>
          )}
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

const StatusPage: React.FC = () => {
  const navigate = useNavigate();
  const { queueNumber } = useParams<{ queueNumber: string }>();
  // T11: the credential comes from this module's memory, never from the query
  // string, so a token in the URL is ignored by design.
  const factor = getGuestFactor();

  // Without an in-memory factor the guest is pointed at the read-only lookup
  // (queue number + last 3 digits of the phone).
  if (!factor || !queueNumber) {
    return (
      <div className="max-w-lg mx-auto p-4">
        <h2 className="text-xl font-bold mb-2">
          Enter the last 3 digits of your phone number
        </h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            navigate('/lookup');
          }}
        >
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

  return <StatusView queueNumber={queueNumber} factor={factor} />;
};

export default StatusPage;
