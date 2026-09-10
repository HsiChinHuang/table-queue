// @vitest-environment jsdom
/**
 * Tests for SettingsPage (F-14): section headings, per-section Save buttons,
 * hold/avg-seat range validation, table CRUD with confirmation, the change-PIN
 * agreement rule, and the dev-only RESET gate.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SettingsPage, {
  isAvgSeatMinutesValid,
  isHoldMinutesValid,
  pinsMatch,
  resetConfirmationOk,
} from './SettingsPage';
import type { Table } from '@/api/tables';

/* eslint-disable @typescript-eslint/no-explicit-any */
type Fn = Mock<(...args: any[]) => unknown>;
const mock = (impl?: (...args: any[]) => unknown) => vi.fn(impl) as unknown as Fn;

const getSettings = mock();
const updateSettings = mock();
const listAdminTables = mock();
const createTable = mock();
const updateTable = mock();
const deleteTable = mock();
const changePin = mock();
const resetData = mock();

vi.mock('@/api/settings', () => ({
  getSettings: (id: string) => getSettings(id),
  updateSettings: (req: any) => updateSettings(req),
}));
vi.mock('@/api/tables', () => ({
  listAdminTables: (id: string) => listAdminTables(id),
  createTable: (req: any) => createTable(req),
  updateTable: (id: string, req: never) => updateTable(id, req),
  deleteTable: (id: string) => deleteTable(id),
}));
vi.mock('@/api/auth', () => ({ changePin: (req: any) => changePin(req) }));
vi.mock('@/api/admin', () => ({ resetData: (id: string) => resetData(id) }));
vi.mock('@/stores/staffStore', () => ({
  staffStore: {
    getState: () => ({ branchId: 'branch-001', token: null }),
    setToken: () => undefined,
    clearToken: () => undefined,
  },
}));

const tables: Table[] = [
  { id: 't1', name: 'A1', capacity: 2, status: 'AVAILABLE' },
  { id: 't2', name: 'B1', capacity: 6, status: 'CLEANING' },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>,
  );
}

const callAt = (fn: Fn, index: number) => (fn.mock.calls[index] as unknown[])[0] as Record<string, unknown>;

beforeEach(() => {
  getSettings.mockResolvedValue({
    branch_id: 'branch-001',
    waitlist_enabled: true,
    call_timeout_minutes: 15,
    queue_prefix: 'A',
    avg_seat_minutes: 20,
    restaurant_name: 'Testaurant',
  } as never);
  listAdminTables.mockResolvedValue(tables as never);
  updateSettings.mockResolvedValue({ success: true } as never);
  createTable.mockResolvedValue(tables[0] as never);
  updateTable.mockResolvedValue(tables[0] as never);
  deleteTable.mockResolvedValue({ success: true } as never);
  changePin.mockResolvedValue({ success: true } as never);
  resetData.mockResolvedValue({ success: true } as never);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('pure validators', () => {
  it('accepts hold minutes inside 5-15 only', () => {
    expect(isHoldMinutesValid(5)).toBe(true);
    expect(isHoldMinutesValid(15)).toBe(true);
    expect(isHoldMinutesValid(4)).toBe(false);
    expect(isHoldMinutesValid(16)).toBe(false);
    expect(isHoldMinutesValid('')).toBe(false);
  });

  it('accepts avg seat minutes inside 5-60 only', () => {
    expect(isAvgSeatMinutesValid(5)).toBe(true);
    expect(isAvgSeatMinutesValid(60)).toBe(true);
    expect(isAvgSeatMinutesValid(61)).toBe(false);
  });

  it('requires both PIN fields to agree and be non-empty', () => {
    expect(pinsMatch('1234', '1234')).toBe(true);
    expect(pinsMatch('1234', '4321')).toBe(false);
    expect(pinsMatch('', '')).toBe(false);
  });

  it('accepts only the literal RESET confirmation', () => {
    expect(resetConfirmationOk('RESET')).toBe(true);
    expect(resetConfirmationOk('reset')).toBe(false);
    expect(resetConfirmationOk('')).toBe(false);
  });
});

describe('sections', () => {
  it('renders the five section headings from ui.md 6.8', async () => {
    renderPage();
    for (const heading of [
      'Store Info',
      'Waitlist Settings',
      'Tables',
      'Notifications & Sound',
      'Danger Zone',
    ]) {
      await waitFor(() => expect(screen.getByText(heading)).toBeTruthy());
    }
  });

  it('has its own Save button per section', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByText('Save').length).toBeGreaterThanOrEqual(4));
  });

  it('shows both range hints', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('call_timeout_minutes 5-15')).toBeTruthy());
    expect(screen.getByText('avg_seat_minutes 5-60')).toBeTruthy();
  });

  it('seeds the store info form from getSettings', async () => {
    renderPage();
    await waitFor(() => expect(getSettings).toHaveBeenCalledWith('branch-001'));
    expect((screen.getByTestId('store-name') as HTMLInputElement).value).toBe('Testaurant');
  });
});

describe('waitlist settings save', () => {
  it('refuses out-of-range hold minutes', async () => {
    renderPage();
    await waitFor(() => expect(getSettings).toHaveBeenCalled());
    fireEvent.change(screen.getByTestId('hold-minutes'), { target: { value: '99' } });
    fireEvent.click(screen.getByTestId('save-waitlist'));
    await waitFor(() => expect(updateSettings).not.toHaveBeenCalled());
    expect(screen.getByText('call_timeout_minutes must be 5-15.')).toBeTruthy();
  });

  it('refuses out-of-range avg seat minutes', async () => {
    renderPage();
    await waitFor(() => expect(getSettings).toHaveBeenCalled());
    fireEvent.change(screen.getByTestId('avg-seat-minutes'), { target: { value: '90' } });
    fireEvent.click(screen.getByTestId('save-waitlist'));
    await waitFor(() => expect(updateSettings).not.toHaveBeenCalled());
    expect(screen.getByText('avg_seat_minutes must be 5-60.')).toBeTruthy();
  });

  it('saves numbers when both ranges are valid', async () => {
    renderPage();
    await waitFor(() => expect(getSettings).toHaveBeenCalled());
    fireEvent.change(screen.getByTestId('hold-minutes'), { target: { value: '10' } });
    fireEvent.click(screen.getByTestId('save-waitlist'));
    await waitFor(() => expect(updateSettings).toHaveBeenCalledTimes(1));
    expect(callAt(updateSettings, 0)).toMatchObject({ call_timeout_minutes: 10, avg_seat_minutes: 20 });
  });

  it('toggles the waitlist switch', async () => {
    renderPage();
    await waitFor(() => expect(getSettings).toHaveBeenCalled());
    const toggle = screen.getByTestId('waitlist-open') as HTMLInputElement;
    expect(toggle.checked).toBe(true);
    fireEvent.click(toggle);
    expect(toggle.checked).toBe(false);
  });
});

describe('tables section', () => {
  it('lists the admin tables', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('A1 (Cap: 2)')).toBeTruthy());
    expect(screen.getByText('B1 (Cap: 6)')).toBeTruthy();
  });

  it('requires a name and a positive capacity before createTable', async () => {
    renderPage();
    await waitFor(() => expect(listAdminTables).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId('add-table'));
    await waitFor(() => expect(createTable).not.toHaveBeenCalled());
    fireEvent.change(screen.getByTestId('new-table-name'), { target: { value: 'C1' } });
    fireEvent.change(screen.getByTestId('new-table-capacity'), { target: { value: '0' } });
    fireEvent.click(screen.getByTestId('add-table'));
    expect(createTable).not.toHaveBeenCalled();
    fireEvent.change(screen.getByTestId('new-table-capacity'), { target: { value: '4' } });
    fireEvent.click(screen.getByTestId('add-table'));
    await waitFor(() => expect(createTable).toHaveBeenCalledTimes(1));
    expect(callAt(createTable, 0)).toEqual({ name: 'C1', capacity: 4 });
  });

  it('edits a table through updateTable', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('A1 (Cap: 2)')).toBeTruthy());
    fireEvent.click(screen.getByTestId('edit-t1'));
    fireEvent.change(screen.getByTestId('edit-name'), { target: { value: 'A9' } });
    fireEvent.change(screen.getByTestId('edit-capacity'), { target: { value: '8' } });
    fireEvent.click(screen.getByTestId('edit-save'));
    await waitFor(() => expect(updateTable).toHaveBeenCalledWith('t1', { name: 'A9', capacity: 8 }));
  });

  it('confirms before deleting', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('A1 (Cap: 2)')).toBeTruthy());
    fireEvent.click(screen.getByTestId('delete-t1'));
    const dialog = await waitFor(() => screen.getByRole('dialog'));
    expect(deleteTable).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByText('Delete'));
    await waitFor(() => expect(deleteTable).toHaveBeenCalledWith('t1'));
  });
});

describe('danger zone', () => {
  it('does not submit a PIN whose confirmation differs', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('pin-input').length).toBe(3));
    const [current, next, confirm] = screen.getAllByTestId('pin-input');
    fireEvent.change(current, { target: { value: '1111' } });
    fireEvent.change(next, { target: { value: '2222' } });
    fireEvent.change(confirm, { target: { value: '3333' } });
    fireEvent.click(screen.getByTestId('change-pin-button'));
    await waitFor(() => expect(changePin).not.toHaveBeenCalled());
    expect(screen.getByText('New PIN and confirmation do not match.')).toBeTruthy();
  });

  it('submits old and new PIN when they agree', async () => {
    renderPage();
    await waitFor(() => expect(screen.getAllByTestId('pin-input').length).toBe(3));
    const [current, next, confirm] = screen.getAllByTestId('pin-input');
    fireEvent.change(current, { target: { value: '1111' } });
    fireEvent.change(next, { target: { value: '9999' } });
    fireEvent.change(confirm, { target: { value: '9999' } });
    fireEvent.click(screen.getByTestId('change-pin-button'));
    await waitFor(() => expect(changePin).toHaveBeenCalledTimes(1));
    expect(callAt(changePin, 0)).toEqual({ old_pin: '1111', new_pin: '9999' });
  });

  it('keeps reset disabled until the user types RESET', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByTestId('reset-input')).toBeTruthy());
    const button = screen.getByTestId('reset-button') as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.change(screen.getByTestId('reset-input'), { target: { value: 'reset' } });
    expect((screen.getByTestId('reset-button') as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(button);
    expect(resetData).not.toHaveBeenCalled();
    fireEvent.change(screen.getByTestId('reset-input'), { target: { value: 'RESET' } });
    expect((screen.getByTestId('reset-button') as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByTestId('reset-button'));
    const dialog = await waitFor(() => screen.getByRole('dialog'));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Reset Data' }));
    await waitFor(() => expect(resetData).toHaveBeenCalledWith('branch-001'));
  });
});
