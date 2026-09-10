# TableQueue — Testing Guide

Version: 0.1.0
Last updated: 2026-09-10

---

## 1. Strategy

- **Backend**: endpoint tests + service tests + state machine tests.
- **Frontend**: API client tests + key component tests.
- **No E2E tests** in v1.
- **No concurrency tests** in v1.
- **Coverage goals**: backend 80%, frontend 70%.
- All tests must run with a single command.

---

## 2. Backend Tests

### Tools
- `pytest`
- `fastapi.testclient.TestClient`
- `freezegun` for time control
- in-memory SQLite for isolation

### Structure

backend/tests/
├── conftest.py
├── factories.py
├── test_auth.py
├── test_public_waitlist.py
├── test_public_board.py
├── test_staff_waitlist.py
├── test_staff_tables.py
├── test_staff_dashboard.py
├── test_admin_settings.py
├── test_admin_tables.py
├── test_state_machine.py
└── test_seed.py


### Fixtures (`conftest.py`)
- `db`: in-memory SQLite session, schema created, closed after test.
- `client`: FastAPI TestClient with `get_db` overridden.
- `fixed_now`: `datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc)`.
- `staff_token`: valid JWT for staff endpoints.
- `auth_headers`: `{"Authorization": f"Bearer {staff_token}"}`.

### Factories (`factories.py`)
- `make_branch(db, **kwargs)`
- `make_table(db, **kwargs)`
- `make_waitlist_entry(db, **kwargs)`
- `make_settings(db, **kwargs)`
- `make_staff_token()`

### Test Names

**Auth**
- `test_login_success`
- `test_login_invalid_pin`
- `test_login_rate_limited`
- `test_change_pin_success`
- `test_change_pin_invalid_current`
- `test_change_pin_mismatch`
- `test_change_pin_same_as_current`

**Public Waitlist**
- `test_join_waitlist_success`
- `test_join_waitlist_duplicate_phone`
- `test_join_waitlist_closed`
- `test_join_waitlist_invalid_phone`
- `test_join_waitlist_party_size_out_of_range`
- `test_join_waitlist_note_too_long`
- `test_get_status_with_token`
- `test_get_status_with_phone_last3`
- `test_get_status_wrong_last3`
- `test_get_status_not_found`
- `test_cancel_waitlist_by_guest`
- `test_cancel_called_requires_confirmation`

**Public Board**
- `test_get_public_branch_success`
- `test_get_public_branch_not_found`
- `test_get_board_success`
- `test_get_board_empty`

**Staff Waitlist**
- `test_list_waitlist_active`
- `test_list_waitlist_closed`
- `test_list_waitlist_all`
- `test_list_waitlist_search_name`
- `test_list_waitlist_search_phone_last3`
- `test_call_waitlist_success`
- `test_call_waitlist_invalid_status`
- `test_seat_waitlist_success`
- `test_seat_waitlist_table_not_available`
- `test_seat_waitlist_table_not_found`
- `test_no_show_waitlist_success`
- `test_no_show_waitlist_invalid_status`
- `test_restore_waitlist_success`
- `test_restore_waitlist_invalid_status`
- `test_revert_waitlist_success`
- `test_revert_waitlist_invalid_status`
- `test_cancel_waitlist_by_staff`
- `test_edit_waitlist_party_size`
- `test_edit_waitlist_note`
- `test_edit_waitlist_invalid_status`
- `test_reorder_waitlist_success`
- `test_reorder_waitlist_missing_ids`
- `test_reorder_waitlist_extra_ids`

**Staff Tables**
- `test_list_tables_active`
- `test_list_tables_includes_current_waitlist`
- `test_update_table_status_available_to_cleaning`
- `test_update_table_status_cleaning_to_available`
- `test_update_table_status_occupied_rejected`
- `test_release_table_success`
- `test_release_table_not_occupied`

**Staff Dashboard**
- `test_dashboard_counts`
- `test_dashboard_avg_wait_null_when_no_data`

**Admin Settings**
- `test_get_settings_success`
- `test_update_settings_success`
- `test_update_settings_hold_minutes_out_of_range`
- `test_update_settings_queue_prefix_invalid`
- `test_update_settings_notification_templates`

**Admin Tables**
- `test_create_table_success`
- `test_create_table_duplicate_label`
- `test_update_table_success`
- `test_update_table_duplicate_label`
- `test_delete_table_soft`
- `test_delete_table_occupied_conflict`
- `test_list_admin_tables_include_inactive`

**State Machine**
- `test_lazy_no_show_after_timeout`
- `test_lazy_no_show_not_yet`
- `test_lazy_no_show_preserves_called_at`
- `test_close_day_closes_active_entries`
- `test_close_day_releases_tables`

**Seed**
- `test_seed_reset_creates_expected_data`
- `test_seed_without_reset_skips_existing`

### Time Injection
- Service functions take `now: datetime` parameter.
- Tests pass fixed time directly, or use `freezegun`.
- Boundary tests:
  - `2026-09-10 03:59` Taipei → `business_date = 2026-09-09`
  - `2026-09-10 04:00` Taipei → `business_date = 2026-09-10`
  - `2026-09-11 01:00` Taipei → `business_date = 2026-09-10`

---

## 3. Frontend Tests

### Tools
- `vitest`
- `@testing-library/react`
- `@testing-library/jest-dom`
- `jsdom` environment

### Structure

frontend/src/
├── api/
│ ├── client.test.ts
│ └── errors.test.ts
├── components/
│ ├── WaitlistCard.test.tsx
│ ├── Countdown.test.tsx
│ ├── TableCard.test.tsx
│ └── StatusBadge.test.tsx
├── pages/
│ ├── JoinPage.test.tsx
│ └── StatusPage.test.tsx
└── test/
├── setup.ts
└── fixtures.ts


### Fixtures (`fixtures.ts`)
- `mockWaitlistEntry(overrides?)`
- `mockTable(overrides?)`
- `mockBranch(overrides?)`
- `mockDashboard(overrides?)`
- `mockBoard(overrides?)`

### Test Names

**API Client**
- `client.test.ts`
  - `adds Authorization header when token exists`
  - `omits Authorization header when no token`
  - `parses error code from 4xx response`
  - `returns null on 204`
  - `throws ApiError on network failure`
  - `throws ApiError on timeout`
- `errors.test.ts`
  - `maps known error codes to messages`
  - `falls back to generic message`

**Components**
- `WaitlistCard.test.tsx`
  - `renders queue number and status`
  - `renders countdown when called`
  - `calls onCall when Call clicked`
  - `calls onSeat when Seat clicked`
- `Countdown.test.tsx`
  - `renders mm:ss format`
  - `turns red at zero`
  - `calls onComplete at zero`
- `TableCard.test.tsx`
  - `renders table label and capacity`
  - `renders occupied info when occupied`
  - `calls onRelease when Release clicked`
- `StatusBadge.test.tsx`
  - `renders correct text for each status`
  - `applies correct color class`

**Pages**
- `JoinPage.test.tsx`
  - `renders form when waitlist open`
  - `shows closed message when waitlist closed`
  - `validates required fields`
  - `validates phone format`
  - `shows duplicate phone error`
- `StatusPage.test.tsx`
  - `renders waiting state`
  - `renders called state with countdown`
  - `renders seated message`
  - `renders cancelled with join again`

---

## 4. Test Data

- Backend factories mirror seed data.
- Frontend fixtures mirror backend response shapes.
- Fixtures use the same queue numbers as seed (`A001`, `A012`).
- Phones use `0900-000-0xx` pattern.
- Dates use `2026-09-10T13:00:00+08:00` as base.

---

## 5. Time Injection

- Backend: `get_now` dependency + `freezegun`.
- Frontend: `Countdown` takes `remainingSeconds` as prop; tests advance timers with `vi.advanceTimersByTime`.
- Never call `Date.now()` inside components without injection.

---

## 6. Coverage Goals

| Layer | Goal |
|---|---|
| Backend services | 80% |
| Backend routers | 80% |
| Frontend API client | 70% |
| Frontend components | 70% |
| Frontend pages | 50% |

- Not enforced in CI in v1.
- Measured manually with `pytest --cov` and `vitest --coverage`.

---

## 7. Non-Goals

- Playwright E2E
- Concurrency tests
- Load tests
- 100% coverage
- Visual regression tests
- Accessibility automated tests (manual only)

---

## 8. Commands

```bash
# Backend
cd backend
uv run pytest
uv run pytest --cov=app
uv run pytest tests/test_state_machine.py -v

# Frontend
cd frontend
npm run test
npm run test -- --coverage
npm run test -- WaitlistCard

# Both
make test