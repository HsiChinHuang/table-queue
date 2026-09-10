# TableQueue — Demo Script

Version: 0.1.0
Last updated: 2026-09-10

---

## Prerequisites

Run the following commands:

```bash
make setup
make seed
make dev
```

Then open your browser.

---

## Seed Data

After `make seed`:

- Restaurant: `Sunny Bistro`
- Branch: `Taipei Xinyi`
- Hours: `11:00–21:00`
- Staff PIN: `1234`
- Tables: `A1–A4` (2 pax), `B1–B4` (4 pax), `C1–C2` (6 pax)
- Waitlist:
  - 5 `WAITING` (different party sizes)
  - 1 `CALLED` (called 3 minutes ago)
  - 1 `SEATED` (occupying `B1`)
  - 1 `NO_SHOW`
  - 1 `CANCELLED`

---

## Step 1: Join Waitlist

1. Open http://localhost:5173/join?branch=1
2. See `Sunny Bistro`, `Taipei Xinyi`, hours, current waiting count.
3. Fill:
   - Name: `Test Guest`
   - Phone: `0900-000-099`
   - Party size: `4`
   - Note: `Window seat`
4. Click `Join Waitlist`.
5. Expect redirect to `/status/A006?token=...`.
6. See:
   - Queue number `A006`
   - Status `Waiting`
   - `N groups ahead`
   - `Estimated wait: X min`
   - Progress bar on step 1.

---

## Step 2: Staff Login

1. Open http://localhost:5173/staff/login
2. Enter PIN: `1234`
3. Click `Login`.
4. Expect redirect to `/staff/waitlist`.
5. See:
   - Stats cards
   - Waitlist list with `A001`–`A005` (waiting), `A006` (waiting, just added), `A012` (called), `A005` (seated), etc.
   - `A012` card shows countdown.

---

## Step 3: Call Next

1. Click `Call` on `A006`.
2. Expect:
   - `A006` status changes to `Called`.
   - Countdown starts (10:00).
   - Card turns orange.

3. Switch to guest tab (status page for `A006`).
4. Expect:
   - Page turns orange.
   - Countdown displayed.
   - Vibration (on mobile).
   - Sound if enabled.
   - Progress bar on step 2.

---

## Step 4: Seat Guest

1. Back in staff tab, click `Seat` on `A006`.
2. Dialog shows available tables sorted by capacity match.
3. Select `A1` (2 pax) — or `B1` if `A006` is 4 pax.
4. Click `Confirm`.
5. Expect:
   - `A006` status changes to `Seated`.
   - Guest status page shows `You're seated. Enjoy your meal!`.
6. Open http://localhost:5173/staff/tables
7. Expect:
   - `A1` (or chosen table) shows `Occupied · A006 · 4 pax · 0 min`.
   - `B1` still shows the seeded seated guest.

---

## Step 5: No-show Flow

1. Back in staff tab, click `Call` on `A001`.
2. Wait 10 minutes, or manually click `No-show` on `A001`.
3. Expect:
   - `A001` status changes to `No-show`.
   - Card turns red.
4. Click `Restore` on `A001`.
5. Expect:
   - `A001` status changes to `Waiting`.
   - Card turns blue.
   - Back in original position.

---

## Step 6: Public Board

1. Open http://localhost:5173/board/1
2. Expect:
   - `Sunny Bistro · Taipei Xinyi`
   - `11:00–21:00`
   - `Now Serving: A006`
   - `Next up: A007` (or next waiting)
   - `Recent calls: A006, A005, A004`
   - `Waiting: N`
   - QR code with `Scan to join the waitlist`
3. Scan QR code with phone (same Wi-Fi).
4. Expect redirect to `/join?branch=1`.

---

## Step 7: Settings

1. Open http://localhost:5173/admin/settings
2. Change `hold_minutes` from `10` to `12`.
3. Click `Save`.
4. Expect toast `Settings updated`.
5. Call a new entry.
6. Expect countdown starts at `12:00`.

---

## Step 8: Release Table

1. Open http://localhost:5173/staff/tables
2. Click `Release Table` on `A1` (or chosen table).
3. Confirm.
4. Expect:
   - Table status changes to `Available`.
   - Corresponding waitlist entry status changes to `Done`.

---

## Step 9: Close Day

1. Open http://localhost:5173/staff/waitlist
2. Click `Close Day`.
3. Confirm.
4. Expect:
   - All `Waiting` and `Called` entries become `Cancelled`.
   - All `Seated` entries become `Done`.
   - All `Occupied` tables become `Cleaning`.

---

## Step 10: Reset (Development Only)

1. Open http://localhost:5173/admin/settings
2. Scroll to Danger Zone.
3. Click `Reset Data`.
4. Type `RESET`.
5. Confirm.
6. Expect:
   - All data reset to seed.
   - Toast `Data reset`.

---

## Demo Checklist

- [ ] Guest can join waitlist
- [ ] Guest sees status page
- [ ] Staff can log in
- [ ] Staff sees waitlist
- [ ] Staff can call
- [ ] Guest sees called state with countdown
- [ ] Staff can seat
- [ ] Table becomes occupied
- [ ] Public board shows current call
- [ ] Staff can mark no-show
- [ ] Staff can restore
- [ ] Staff can release table
- [ ] Staff can close day
- [ ] Admin can change settings
- [ ] Admin can reset data (dev only)