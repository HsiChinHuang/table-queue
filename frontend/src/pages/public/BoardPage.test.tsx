// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import BoardPage, { buildJoinUrl, limitRecentCalls } from './BoardPage';
import type { BoardResponse, PublicBranch, WaitlistEntry } from '@/api/public';

const entry = (queue_number: string) => ({ queue_number }) as unknown as WaitlistEntry;

import * as publicApi from '@/api/public';

vi.mock('@/api/public', () => ({
  getBoard: vi.fn(),
  getPublicBranch: vi.fn(),
}));

const mockGetBoard = vi.mocked(publicApi.getBoard);
const mockGetPublicBranch = vi.mocked(publicApi.getPublicBranch);

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('buildJoinUrl', () => {
  it('builds the join URL from a base without a trailing slash', () => {
    expect(buildJoinUrl('https://t.example', 'branch-001')).toBe(
      'https://t.example/join?branch=branch-001',
    );
  });

  it('strips trailing slashes', () => {
    expect(buildJoinUrl('https://t.example/', 'branch-001')).toBe(
      'https://t.example/join?branch=branch-001',
    );
  });

  it('works with an empty base', () => {
    expect(buildJoinUrl('', '1')).toBe('/join?branch=1');
  });
});

describe('limitRecentCalls', () => {
  it('keeps short lists intact', () => {
    expect(limitRecentCalls(['A01', 'A02'])).toEqual(['A01', 'A02']);
  });

  it('caps at three entries', () => {
    expect(limitRecentCalls(['A01', 'A02', 'A03', 'A04', 'A05'])).toEqual(['A01', 'A02', 'A03']);
  });

  it('handles an empty list', () => {
    expect(limitRecentCalls([])).toEqual([]);
  });
});

describe('BoardPage', () => {
  const board: BoardResponse = {
    branch_id: '1',
    waiting_count: 5,
    current_call: entry('A001'),
    next_up: entry('A002'),
    recent_calls: [entry('A003'), entry('A004'), entry('A005'), entry('A006')],
  };
  const info: PublicBranch = {
    id: '1',
    name: 'Main',
    restaurant_id: 'r1',
    timezone: 'UTC',
    cutoff_hour: 22,
    restaurant_name: 'Testaurant',
    branch_name: 'Main',
    hours: '9am-5pm',
    waiting_count: 5,
    is_waitlist_open: true,
  };

  beforeEach(() => {
    mockGetBoard.mockResolvedValue(board);
    mockGetPublicBranch.mockResolvedValue(info);
  });

  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={['/board/1']}>
        <Routes>
          <Route path="/board/:branchId" element={<BoardPage />} />
        </Routes>
      </MemoryRouter>,
    );

  it('polls the board every five seconds', async () => {
    vi.useFakeTimers();
    try {
      renderPage();
      await vi.waitFor(() => expect(mockGetBoard).toHaveBeenCalledTimes(1));
      await vi.advanceTimersByTimeAsync(5000);
      expect(mockGetBoard).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('renders now serving, next up and the capped recent calls', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Now Serving')).toBeTruthy());
    expect(screen.getByText('A001')).toBeTruthy();
    expect(screen.getByText('A002')).toBeTruthy();
    expect(screen.getByText('A003')).toBeTruthy();
    expect(screen.queryByText('A006')).toBeNull();
    expect(screen.getByText('Waiting: 5')).toBeTruthy();
  });

  it('shows the closed message when the waitlist is closed', async () => {
    mockGetPublicBranch.mockResolvedValue({ ...info, is_waitlist_open: false });
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('Waitlist is currently closed.')).toBeTruthy(),
    );
  });

  it('links to the join page when opened', async () => {
    mockGetPublicBranch.mockResolvedValue({ ...info, is_waitlist_open: true });
    renderPage();
    await waitFor(() => expect(screen.queryByText('Waitlist is currently closed.')).toBeNull());
    expect(screen.getByText('Scan to join the waitlist')).toBeTruthy();
  });
});
