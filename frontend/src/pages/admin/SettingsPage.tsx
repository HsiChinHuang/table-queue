// SettingsPage - admin settings: five sections, each with its own Save button.
// Design source: _docs/ui.md section 6.8. API surface: @/api/settings, @/api/tables,
// @/api/auth, @/api/admin.

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Switch } from '@/components/ui/Switch';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { getSettings, updateSettings } from '@/api/settings';
import type { Settings, UpdateSettingsRequest } from '@/api/settings';
import { listAdminTables, createTable, updateTable, deleteTable } from '@/api/tables';
import type { Table } from '@/api/tables';
import { changePin } from '@/api/auth';
import { resetData } from '@/api/admin';
import { staffStore } from '@/stores/staffStore';

export const HOLD_MIN_MINUTES = 5;
export const HOLD_MAX_MINUTES = 15;
export const AVG_SEAT_MIN_MINUTES = 5;
export const AVG_SEAT_MAX_MINUTES = 60;
export const RESET_WORD = 'RESET';

/** hold_minutes range hint is `5-15` (ui.md 6.8). */
export function isHoldMinutesValid(value: unknown): boolean {
  const n = Number(value);
  return Number.isFinite(n) && n >= HOLD_MIN_MINUTES && n <= HOLD_MAX_MINUTES;
}

/** avg_seat_minutes range hint is `5-60` (ui.md 6.8). */
export function isAvgSeatMinutesValid(value: unknown): boolean {
  const n = Number(value);
  return Number.isFinite(n) && n >= AVG_SEAT_MIN_MINUTES && n <= AVG_SEAT_MAX_MINUTES;
}

/** A new PIN is only submitted when both fields agree and are non-empty. */
export function pinsMatch(newPin: string, confirmPin: string): boolean {
  return newPin.length > 0 && newPin === confirmPin;
}

/** Destructive reset requires typing the literal word RESET. */
export function resetConfirmationOk(value: string): boolean {
  return value === RESET_WORD;
}

function getStaffBranchId(): string {
  const state = staffStore.getState() as { branchId?: string | number };
  return state.branchId != null ? String(state.branchId) : 'branch-001';
}

interface DraftTable {
  name: string;
  capacity: string;
}

export default function SettingsPage() {
  const branchId = getStaffBranchId();

  const [settings, setSettings] = useState<Settings | null>(null);
  const [tables, setTables] = useState<Table[]>([]);
  const [newTable, setNewTable] = useState<DraftTable>({ name: '', capacity: '' });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftTable>({ name: '', capacity: '' });
  const [tableToDelete, setTableToDelete] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [currentPin, setCurrentPin] = useState('');
  const [newPin, setNewPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [resetInput, setResetInput] = useState('');
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getSettings(branchId)
      .then((data) => {
        if (alive) setSettings(data);
      })
      .catch(() => {
        if (alive) setMessage('Failed to load settings.');
      });
    listAdminTables(branchId)
      .then((data) => {
        if (alive) setTables(data);
      })
      .catch(() => {
        if (alive) setMessage('Failed to load tables.');
      });
    return () => {
      alive = false;
    };
  }, [branchId]);

  const patch = (changes: Partial<Settings>) => {
    setSettings((prev) => ({ ...(prev ?? { branch_id: branchId }), ...changes } as Settings));
  };

  const saveStoreInfo = async () => {
    if (!settings) return;
    const request: UpdateSettingsRequest = {
      restaurant_name: settings.restaurant_name,
      address: settings.address,
      phone: settings.phone,
      open_time: settings.open_time,
      close_time: settings.close_time,
    };
    await updateSettings(request);
    setMessage('Store info saved.');
  };

  const saveWaitlist = async () => {
    if (!settings) return;
    if (!isHoldMinutesValid(settings.call_timeout_minutes)) {
      setMessage(`call_timeout_minutes must be ${HOLD_MIN_MINUTES}-${HOLD_MAX_MINUTES}.`);
      return;
    }
    if (!isAvgSeatMinutesValid(settings.avg_seat_minutes)) {
      setMessage(`avg_seat_minutes must be ${AVG_SEAT_MIN_MINUTES}-${AVG_SEAT_MAX_MINUTES}.`);
      return;
    }
    await updateSettings({
      waitlist_enabled: settings.waitlist_enabled,
      call_timeout_minutes: Number(settings.call_timeout_minutes),
      queue_prefix: settings.queue_prefix,
      avg_seat_minutes: Number(settings.avg_seat_minutes),
    });
    setMessage('Waitlist settings saved.');
  };

  const addTable = async () => {
    const capacity = Number(newTable.capacity);
    if (!newTable.name || !Number.isFinite(capacity) || capacity < 1) {
      setMessage('Table name and a capacity of at least 1 are required.');
      return;
    }
    await createTable({ name: newTable.name, capacity });
    setNewTable({ name: '', capacity: '' });
    setTables(await listAdminTables(branchId));
    setMessage('Table added.');
  };

  const startEdit = (table: Table) => {
    setEditingId(table.id);
    setDraft({ name: table.name, capacity: String(table.capacity) });
  };

  const saveEdit = async (tableId: string) => {
    const capacity = Number(draft.capacity);
    if (!draft.name || !Number.isFinite(capacity) || capacity < 1) {
      setMessage('Table name and a capacity of at least 1 are required.');
      return;
    }
    await updateTable(tableId, { name: draft.name, capacity });
    setEditingId(null);
    setTables(await listAdminTables(branchId));
    setMessage('Table updated.');
  };

  const confirmDeleteTable = async () => {
    if (tableToDelete) {
      await deleteTable(tableToDelete);
      setTables(await listAdminTables(branchId));
      setMessage('Table deleted.');
    }
    setDeleteDialogOpen(false);
    setTableToDelete(null);
  };

  const saveNotifications = async () => {
    if (!settings) return;
    await updateSettings({ sound_enabled_default: settings.sound_enabled_default });
    setMessage('Notifications saved.');
  };

  const changePinHandler = async () => {
    if (!pinsMatch(newPin, confirmPin)) {
      setMessage('New PIN and confirmation do not match.');
      return;
    }
    await changePin({ old_pin: currentPin, new_pin: newPin });
    setCurrentPin('');
    setNewPin('');
    setConfirmPin('');
    setMessage('PIN changed.');
  };

  const confirmReset = async () => {
    if (!resetConfirmationOk(resetInput)) {
      setMessage(`Type ${RESET_WORD} to enable the reset.`);
      return;
    }
    await resetData(branchId);
    setResetDialogOpen(false);
    setMessage('Data reset.');
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8 p-4">
      {message && <p className="text-sm text-muted-foreground">{message}</p>}

      {/* 1. Store Info */}
      <section>
        <h2 className="mb-4 text-2xl font-semibold">Store Info</h2>
        <div className="grid gap-2">
          <Label htmlFor="store-name">Restaurant Name</Label>
          <Input
            id="store-name"
            data-testid="store-name"
            value={settings?.restaurant_name ?? ''}
            onChange={(e) => patch({ restaurant_name: e.target.value })}
          />
          <Label htmlFor="store-address">Address</Label>
          <Input
            id="store-address"
            data-testid="store-address"
            value={settings?.address ?? ''}
            onChange={(e) => patch({ address: e.target.value })}
          />
          <Label htmlFor="store-phone">Phone</Label>
          <Input
            id="store-phone"
            data-testid="store-phone"
            value={settings?.phone ?? ''}
            onChange={(e) => patch({ phone: e.target.value })}
          />
          <Label htmlFor="store-open">Open Time</Label>
          <Input
            id="store-open"
            data-testid="store-open"
            value={settings?.open_time ?? ''}
            onChange={(e) => patch({ open_time: e.target.value })}
          />
          <Label htmlFor="store-close">Close Time</Label>
          <Input
            id="store-close"
            data-testid="store-close"
            value={settings?.close_time ?? ''}
            onChange={(e) => patch({ close_time: e.target.value })}
          />
        </div>
        <Button className="mt-2" data-testid="save-store" onClick={saveStoreInfo}>Save</Button>
      </section>

      {/* 2. Waitlist Settings */}
      <section>
        <h2 className="mb-4 text-2xl font-semibold">Waitlist Settings</h2>
        <div className="grid gap-2">
          <Label htmlFor="waitlist-open">Waitlist Open</Label>
          <Switch
            id="waitlist-open"
            data-testid="waitlist-open"
            checked={Boolean(settings?.waitlist_enabled)}
            onCheckedChange={(checked) => patch({ waitlist_enabled: checked })}
          />
          <Label htmlFor="hold-minutes">Hold / call timeout minutes</Label>
          <Input
            id="hold-minutes"
            data-testid="hold-minutes"
            value={settings?.call_timeout_minutes ?? ''}
            onChange={(e) => patch({ call_timeout_minutes: Number(e.target.value) })}
          />
          <p className="text-xs text-muted-foreground">call_timeout_minutes 5-15</p>
          <Label htmlFor="avg-seat-minutes">Average Seat Minutes</Label>
          <Input
            id="avg-seat-minutes"
            data-testid="avg-seat-minutes"
            value={settings?.avg_seat_minutes ?? ''}
            onChange={(e) => patch({ avg_seat_minutes: Number(e.target.value) })}
          />
          <p className="text-xs text-muted-foreground">avg_seat_minutes 5-60</p>
          <Label htmlFor="queue-prefix">Queue Prefix</Label>
          <Input
            id="queue-prefix"
            data-testid="queue-prefix"
            value={settings?.queue_prefix ?? ''}
            onChange={(e) => patch({ queue_prefix: e.target.value })}
          />
        </div>
        <Button className="mt-2" data-testid="save-waitlist" onClick={saveWaitlist}>Save</Button>
      </section>

      {/* 3. Tables */}
      <section>
        <h2 className="mb-4 text-2xl font-semibold">Tables</h2>
        <div className="flex items-end gap-2">
          <div className="grid gap-1">
            <Label htmlFor="new-table-name">Name</Label>
            <Input
              id="new-table-name"
              data-testid="new-table-name"
              value={newTable.name}
              onChange={(e) => setNewTable({ ...newTable, name: e.target.value })}
            />
          </div>
          <div className="grid gap-1">
            <Label htmlFor="new-table-capacity">Capacity</Label>
            <Input
              id="new-table-capacity"
              data-testid="new-table-capacity"
              value={newTable.capacity}
              onChange={(e) => setNewTable({ ...newTable, capacity: e.target.value })}
            />
          </div>
          <Button data-testid="add-table" onClick={addTable}>Add Table</Button>
        </div>
        <ul className="mt-2 grid gap-2">
          {tables.map((t) => (
            <li key={t.id} className="flex items-center justify-between border p-2">
              {editingId === t.id ? (
                <>
                  <Input
                    aria-label="Table name"
                    data-testid="edit-name"
                    value={draft.name}
                    onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  />
                  <Input
                    aria-label="Table capacity"
                    data-testid="edit-capacity"
                    value={draft.capacity}
                    onChange={(e) => setDraft({ ...draft, capacity: e.target.value })}
                  />
                  <Button data-testid="edit-save" onClick={() => saveEdit(t.id)}>Save</Button>
                </>
              ) : (
                <>
                  <span>
                    {t.name} (Cap: {t.capacity})
                  </span>
                  <span className="space-x-2">
                    <Button data-testid={`edit-${t.id}`} onClick={() => startEdit(t)}>Edit</Button>
                    <Button
                      data-testid={`delete-${t.id}`}
                      onClick={() => {
                        setTableToDelete(t.id);
                        setDeleteDialogOpen(true);
                      }}
                    >
                      Delete
                    </Button>
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
        <ConfirmDialog
          open={deleteDialogOpen}
          onClose={() => setDeleteDialogOpen(false)}
          onConfirm={confirmDeleteTable}
          title="Delete Table"
          description="Are you sure you want to delete this table?"
          variant="danger"
          confirmLabel="Delete"
        />
      </section>

      {/* 4. Notifications & Sound */}
      <section>
        <h2 className="mb-4 text-2xl font-semibold">Notifications & Sound</h2>
        <p className="text-sm text-muted-foreground">
          Notification templates are not exposed by the API yet; they arrive with the backend.
        </p>
        <Label htmlFor="sound-default">Default Sound Enabled</Label>
        <Switch
          id="sound-default"
          checked={Boolean(settings?.sound_enabled_default)}
          onCheckedChange={(checked) => patch({ sound_enabled_default: checked })}
        />
        <Button className="mt-2" data-testid="save-notifications" onClick={saveNotifications}>Save</Button>
      </section>

      {/* 5. Danger Zone */}
      <section>
        <h2 className="mb-4 text-2xl font-semibold">Danger Zone</h2>
        <div className="grid gap-2">
          <Label htmlFor="current-pin">Current PIN</Label>
          <Input
            id="current-pin"
            type="password"
            data-testid="pin-input"
            value={currentPin}
            onChange={(e) => setCurrentPin(e.target.value)}
          />
          <Label htmlFor="new-pin">New PIN</Label>
          <Input
            id="new-pin"
            type="password"
            data-testid="pin-input"
            value={newPin}
            onChange={(e) => setNewPin(e.target.value)}
          />
          <Label htmlFor="confirm-pin">Confirm New PIN</Label>
          <Input
            id="confirm-pin"
            type="password"
            data-testid="pin-input"
            value={confirmPin}
            onChange={(e) => setConfirmPin(e.target.value)}
          />
        </div>
        <Button className="mt-2" data-testid="change-pin-button" onClick={changePinHandler}>
          Save
        </Button>
        {import.meta.env.DEV && (
          <div className="mt-4">
            <Label htmlFor="reset-input">Type RESET to confirm</Label>
            <Input
              id="reset-input"
              data-testid="reset-input"
              value={resetInput}
              onChange={(e) => setResetInput(e.target.value)}
            />
            <Button
              className="mt-2"
              data-testid="reset-button"
              disabled={!resetConfirmationOk(resetInput)}
              onClick={() => setResetDialogOpen(true)}
            >
              Reset Data
            </Button>
            <ConfirmDialog
              open={resetDialogOpen}
              onClose={() => setResetDialogOpen(false)}
              onConfirm={confirmReset}
              title="Reset Data"
              description="This will erase all data in this branch."
              variant="danger"
              confirmLabel="Reset Data"
            />
          </div>
        )}
      </section>
    </div>
  );
}
