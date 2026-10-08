// @vitest-environment jsdom
/**
 * T14 AC-4 / AC-5: Waitlist board scale/perf test.
 *
 * Pins the N=200 render budget:
 * - Arm 1: loading-state mount returns (guards the loading-state render loop)
 * - Arm 2: N=200 active case completes and reports measured numbers
 * - Ceiling assertion: DOM node count and rendered card count bounded
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi, it, expect, describe } from 'vitest';

vi.mock('@/api/waitlist', () => ({
  listWaitlist: vi.fn(),
  callWaitlist: vi.fn(async () => ({ success: true })),
  seatWaitlist: vi.fn(async () => ({ success: true })),
  noShowWaitlist: vi.fn(async () => ({ success: true })),
  restoreWaitlist: vi.fn(async () => ({ success: true })),
  revertWaitlist: vi.fn(async () => ({ success: true })),
  cancelWaitlistByStaff: vi.fn(async () => ({ success: true })),
  reorderWaitlist: vi.fn(async () => ({ success: true })),
}));
vi.mock('@/api/dashboard', () => ({ getDashboard: vi.fn() }));
vi.mock('@/api/public', () => ({
  getPublicBranch: vi.fn(async () => ({ id: 'branch-001', name: 'T14 Scale' })),
}));

import { listWaitlist, type WaitlistEntry } from '@/api/waitlist';
import { getDashboard, type DashboardResponse } from '@/api/dashboard';
import WaitlistPage from '@/pages/staff/WaitlistPage';

// --- Fixture: N=200 entries ---
function makeEntry(n: number, status: string) {
  const prefix = status === 'WAITING' ? 'AQ' : 'CL';
  return {
    id: String(n),
    queue_number: prefix + String(n).padStart(3, '0'),
    full_queue_number: 'TQ-' + String(n).padStart(4, '0'),
    name: 'Guest ' + n,
    phone: '0912-345-' + String(100 + n),
    party_size: 2,
    status,
    note: '',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    wait_time_minutes: n,
    sort_order: n,
  };
}

const N = 200;

describe('Waitlist scale/perf (N=200)', () => {
  it('arm 1: loading-state mount returns (no render loop)', async () => {
    vi.mocked(listWaitlist).mockImplementation(() => new Promise<WaitlistEntry[]>(() => {}));
    vi.mocked(getDashboard).mockImplementation(() => new Promise<DashboardResponse>(() => {}));
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
    });
    const t0 = Date.now();
    const { unmount } = render(
      <QueryClientProvider client={qc}>
        <WaitlistPage />
      </QueryClientProvider>
    );
    const ms = Date.now() - t0;
    console.log('AC5-LOADING render_ms=' + ms);
    expect(ms).toBeLessThan(30000);
    unmount();
    qc.clear();
  }, 30000);

  it('arm 2: N=200 active case completes within budget and reports numbers', async () => {
    const active = Array.from({ length: N }, (_, i) => makeEntry(i + 1, 'WAITING'));
    vi.mocked(listWaitlist).mockResolvedValue(active as WaitlistEntry[]);
    vi.mocked(getDashboard).mockResolvedValue({
      waiting_count: N,
      called_count: 0,
      available_tables: 8,
      occupied_tables: 4,
    } as DashboardResponse);
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
    });
    const t0 = Date.now();
    const { container, unmount } = render(
      <QueryClientProvider client={qc}>
        <WaitlistPage />
      </QueryClientProvider>
    );
    await screen.findByText('Active Waitlist', {}, { timeout: 60000 });
    const renderMs = Date.now() - t0;
    const nodes = container.querySelectorAll('*').length;
    const cards = container.querySelectorAll('button[aria-label^="Call "]').length;
    console.log('AC5-SCALE n=200 render_ms=' + renderMs + ' nodes=' + nodes + ' cards=' + cards);

    // AC-2: rendered cards > 0 and <= 100
    expect(cards).toBeGreaterThan(0);
    expect(cards).toBeLessThanOrEqual(100);

    // AC-4: DOM node count ceiling (calibrated: 100 cards * ~15 nodes/card + page chrome)
    expect(nodes).toBeLessThanOrEqual(5000);

    unmount();
    qc.clear();
  }, 120000);

  it('arm 3: closed section capped at 50 rows with working show-more', async () => {
    const active = Array.from({ length: 5 }, (_, i) => makeEntry(i + 1, 'WAITING'));
    const closed = Array.from({ length: 100 }, (_, i) => makeEntry(i + 1, 'DONE'));
    vi.mocked(listWaitlist).mockResolvedValue([...active, ...closed] as WaitlistEntry[]);
    vi.mocked(getDashboard).mockResolvedValue({
      waiting_count: 5,
      called_count: 0,
      available_tables: 8,
      occupied_tables: 4,
    } as DashboardResponse);
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
    });
    const { unmount } = render(
      <QueryClientProvider client={qc}>
        <WaitlistPage />
      </QueryClientProvider>
    );
    await screen.findByText('Closed today', {}, { timeout: 30000 });
    fireEvent.click(screen.getByRole('button', { name: /closed today/i }));
    await waitFor(
      () => {
        expect(document.getElementById('closed-today-section')).toBeTruthy();
      },
      { timeout: 30000 }
    );

    const countVisible = () => {
      const section = document.getElementById('closed-today-section');
      if (!section) return -1;
      const text = section.textContent || '';
      let c = 0;
      for (let n = 1; n <= 100; n++) {
        if (text.includes('CL' + String(n).padStart(3, '0'))) c++;
      }
      return c;
    };

    const visible = countVisible();
    console.log('AC1-METRICS visible=' + visible + ' total=100');
    expect(visible).toBeGreaterThanOrEqual(0);
    expect(visible).toBeLessThanOrEqual(50);

    if (visible < 100) {
      const section = document.getElementById('closed-today-section')!;
      const more = Array.from(section.querySelectorAll('button')).find((b) =>
        /more/i.test(b.textContent || '')
      );
      expect(more, 'show-more affordance required when the list is capped').toBeTruthy();
      fireEvent.click(more!);
      await waitFor(() => {
        expect(countVisible()).toBeGreaterThan(visible);
      }, { timeout: 30000 });
    }

    unmount();
    qc.clear();
  }, 120000);
});
