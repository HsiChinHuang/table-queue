import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import { getBoard, getPublicBranch } from '@/api/public';

/** Join URL for the QR code. AC-8 requires the literal '/join?branch=' shape. */
export function buildJoinUrl(publicBaseUrl: string, branchId: string): string {
  const base = publicBaseUrl.replace(/\/+$/, '');
  return `${base}/join?branch=${branchId}`;
}

/** The board shows at most three recent calls. */
export function limitRecentCalls<T>(list: readonly T[]): T[] {
  return list.slice(0, 3);
}

/** Board poller: 5000ms interval plus a refresh on window focus. */
function useBoard(branchId: string) {
  const [board, setBoard] = useState<Awaited<ReturnType<typeof getBoard>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!branchId) return;
    let alive = true;
    const load = () => {
      getBoard(branchId)
        .then((data) => {
          if (!alive) return;
          setBoard(data);
          setError(null);
        })
        .catch((err: unknown) => {
          if (alive) setError(err instanceof Error ? err.message : 'Error loading board');
        });
    };
    load();
    const interval = window.setInterval(load, 5000);
    const onFocus = () => load();
    window.addEventListener('focus', onFocus);
    return () => {
      alive = false;
      window.clearInterval(interval);
      window.removeEventListener('focus', onFocus);
    };
  }, [branchId]);

  return { board, error };
}

function useBranchInfo(branchId: string) {
  const [info, setInfo] = useState<Awaited<ReturnType<typeof getPublicBranch>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!branchId) return;
    let alive = true;
    getPublicBranch(branchId)
      .then((data) => {
        if (alive) setInfo(data);
      })
      .catch((err: unknown) => {
        if (alive) setError(err instanceof Error ? err.message : 'Error loading branch');
      });
    return () => {
      alive = false;
    };
  }, [branchId]);

  return { info, error };
}

const RECENT_LIMIT = 3;

export default function BoardPage() {
  const { branchId = '' } = useParams<{ branchId: string }>();
  const { board, error: boardError } = useBoard(branchId);
  const { info, error: infoError } = useBranchInfo(branchId);

  if (boardError || infoError) {
    return <div className="p-4 text-destructive">Failed to load data.</div>;
  }

  if (!board || !info) {
    return <div className="p-4">Loading...</div>;
  }

  const recent = limitRecentCalls(board.recent_calls).slice(0, RECENT_LIMIT);

  return (
    <div className="mx-auto max-w-4xl p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="space-y-2">
        <h1 className="text-xl font-bold">{info.restaurant_name}</h1>
        <p className="text-lg">{info.branch_name}</p>
        <p className="text-sm text-muted-foreground">{info.hours}</p>
        <div className="mt-4 flex flex-col items-center gap-2">
          <QRCodeSVG value={buildJoinUrl(window.location.origin, branchId)} size={128} />
          <p className="text-sm">Scan to join the waitlist</p>
        </div>
        {!info.is_waitlist_open && (
          <p className="font-semibold text-destructive">Waitlist is currently closed.</p>
        )}
      </div>

      <div className="space-y-2">
        <p className="text-2xl font-bold">Now Serving</p>
        <p className="font-mono text-6xl">{board.current_call?.queue_number ?? '--'}</p>
        <p className="text-xl font-bold">Next up</p>
        <p className="font-mono text-4xl">{board.next_up?.queue_number ?? '--'}</p>
        <p className="text-xl font-bold">Recent calls</p>
        <ul className="flex gap-2">
          {recent.map((call) => (
            <li key={call.queue_number} className="rounded bg-muted px-2 py-1 font-mono">
              {call.queue_number}
            </li>
          ))}
        </ul>
        <p className="text-xl font-bold">Waiting: {board.waiting_count}</p>
      </div>
    </div>
  );
}
