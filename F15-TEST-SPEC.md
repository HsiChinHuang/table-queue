# F-15 concrete test specification (orchestrator-authored, no ambiguity)

Ground truth verified in /home/te/tq/F-15 at 627828a8:
- Kit files that EXIST: components/{Countdown,WaitlistCard,TableCard,EmptyState,StatusBadge,
  ConfirmDialog,ConnectionBanner,DevBadge,LoadingSkeleton,SoundToggle,QrCode,index}.tsx/ts,
  hooks/useCountdown.ts, api/{client,errors,staffStore,queryKeys,...}.ts, layouts/{PublicLayout,
  StaffLayout}.tsx, pages/NotFoundPage.tsx.
- Kit files that DO NOT exist (do not create, do not test): CountdownTimer.tsx, ErrorBanner.tsx.
  AC-1 names only files that are genuinely absent today.
- Existing tests (9 files, 105 tests): pages/**.test.tsx, stores/staffStore.test.ts.
- vite.config.ts test block is currently `{ environment: 'node' }` with NO setupFiles.
- client.ts exports: get, post, put, patch, del, API_BASE_URL; it reads staffStore.token,
  uses fetch + AbortController(30000ms), returns null on 204, throws ApiError on non-2xx,
  and short-circuits to mockRequest() when import.meta.env.VITE_USE_MOCK === 'true'.
- errors.ts exports: ERROR_MESSAGES (Record<string,string>), class ApiError extends Error,
  getErrorMessage(code), isApiError(unknown).
- useCountdown.ts exports: useCountdown(targetTime: Date|number, onComplete?) ->
  { remainingSeconds, start, stop, isRunning } (interval-based, Math.max(0, ceil((target-Date.now())/1000))).
- components/index.ts re-exports every component; import components from '@/components' or the file.

RULES
- Every DOM test file starts with a line: `// @vitest-environment jsdom`
  (the project default environment is node; without the pragma `document` is undefined).
- Use plain expect + DOM properties (textContent, value, href, disabled, .checked,
  getAttribute, querySelector). Do NOT use jest-dom matchers (toBeInTheDocument etc.)
  except in files that are guaranteed to load setup.ts — safest: avoid them everywhere.
- Use vi.stubGlobal('fetch', ...) or vi.fn() fakes; never hit the network.
- Cleanup: import { cleanup } from '@testing-library/react' and call it in afterEach.
- Do NOT touch: package.json, package-lock.json, src/api/client.ts, src/api/errors.ts,
  components/ui/*, lib/utils.ts, anything under _docs/.
- frontend/vite.config.ts IS in scope and you MUST edit it: AC-4 REQUIRES the string "setupFiles" to appear in it.
  Make the minimal edit: test block becomes
    test: { environment: 'node', setupFiles: ['./src/test/setup.ts'] }
  and add a coverage block with `provider: 'v8'`, `reportsDirectory: './coverage'`,
  `include: ['src/**/*.{ts,tsx}']`, `exclude: ['src/**/*.test.*', 'src/test/**', 'src/main.tsx', 'src/vite-env.d.ts']`.
  Keep plugins/alias/server untouched. Report this file in your finish block.

FILE 1 — frontend/src/test/setup.ts (AC-4)
  Content: `import '@testing-library/jest-dom';` plus a comment line. Nothing else needed
  (do not call cleanup() here; each test file does it).
  NOTE: the file must contain the literal string `@testing-library/jest-dom`.

FILE 2 — frontend/src/test/fixtures.ts (AC-5)
  Must export EXACTLY these five named consts (grep pattern is `export const <name>`):
    mockWaitlistEntry, mockTable, mockBranch, mockDashboard, mockBoard
  Shapes must satisfy the TS types of the code under test (read the source first):
    - mockWaitlistEntry: matches WaitlistCard props/entry shape in components/WaitlistCard.tsx
      (id: number, queueNumber: string, name: string, phone: string, partySize: number,
      status-ish fields as declared, note?: string, waitMinutes?: number, holdMinutes?: number).
      Use a deterministic literal, e.g. { id: 1, queueNumber: 'A001', name: 'Alice',
      phone: '0900-000-001', partySize: 4, note: 'Window seat', waitMinutes: 12, holdMinutes: 15 }.
    - mockTable: matches TableCard's TableData (id: number, label: string, capacity: number,
      plus its nested occupant object with queueNumber + partySize if required).
    - mockBranch: a public branch object (see api/public.ts / api/mock/seed.ts branch fields).
    - mockDashboard: an object usable by DashboardResponse consumers (read api/dashboard.ts).
    - mockBoard: an object usable by BoardPage's board state (branch + tables + waitlist arrays).
  Add `export type` helpers only if needed. Every fixture must be plain data (no functions).
  ALSO add `export const fixtureNames = [...]`? NO — not required; keep the five exports.

FILE 3 — frontend/src/api/client.test.ts (AC-6: >=70% statements of client.ts)
  Import { get, post, put, patch, del, API_BASE_URL } from '@/api/client' and
  { staffStore } from '@/api/staffStore' (or set the token via its exported API — read the file).
  Tests (all with a fetch stub):
   1. get() returns parsed JSON and calls fetch with `${API_BASE_URL}${path}` and GET.
   2. get() sends Authorization: Bearer <token> after the token is set (set it via the store's
      public setter, and reset it in afterEach).
   3. get() returns null when the response status is 204.
   4. get() throws ApiError for a non-2xx response (assert error instanceof ApiError and that
      error.code/message come from the JSON error body; read client.ts's error branch first).
   5. post() passes method POST plus a JSON.stringify(body) body and returns parsed JSON.
   6. put() sends PUT; patch() sends PATCH; del() sends DELETE (three small assertions, or a
      table-driven loop over [put,'PUT'],[patch,'PATCH'],[del,'DELETE']).
   7. custom headers are merged: get(path, { 'X-Test': '1' }) sends X-Test.
   8. mock mode: vi.stubEnv('VITE_USE_MOCK', 'true') (or set import.meta.env value via
      vi.stubEnv) then get('/anything') resolves without fetch being called (mock branch).
   9. getErrorMessage / ApiError behaviour that client.ts relies on may be covered in FILE 4.
  Fetch stub helper: returns { ok, status, json: async () => body }. Use
  vi.stubGlobal('fetch', fetchMock) in beforeEach, vi.unstubAllGlobals() in afterEach.
  IMPORTANT: cover BOTH branches (mock on/off), the 204 branch, the error branch and the
  token branch — that is what pushes statements past 70%.

FILE 4 — frontend/src/api/errors.test.ts (AC-6: >=70% of errors.ts)
  Import { ApiError, getErrorMessage, isApiError, ERROR_MESSAGES } from '@/api/errors'.
  Tests:
   1. new ApiError(...) sets .message, .code, .status per its constructor signature (read it)
      and instanceof Error + instanceof ApiError.
   2. getErrorMessage(known code) returns ERROR_MESSAGES[code] (iterate Object.keys and assert
      each returns a non-empty string).
   3. getErrorMessage('NOT_A_REAL_CODE') returns the documented fallback (read the function —
      assert exactly what it returns, e.g. the code itself or a generic message).
   4. isApiError(new ApiError(...)) === true; false for new Error('x'), 'string', null, {},
      and { code: 'X' } (duck-typing check only if the implementation does that — read it).

FILE 5 — frontend/src/hooks/useCountdown.test.ts (AC-8: fake timers, file name must contain
  the literal `useFakeTimers`)
  Pragma line 1: `// @vitest-environment jsdom`
  Use a tiny harness component (render a <span>{remainingSeconds}</span> + buttons calling
  start/stop) — do NOT import @testing-library/react-hooks (not installed).
  Tests (each: vi.useFakeTimers() in beforeEach, vi.advanceTimersByTime(n*1000),
  vi.useRealTimers() in afterEach):
   1. initial remainingSeconds = ceil((target - Date.now())/1000) (e.g. Date.now()+90_000 -> 90).
   2. after start() and vi.advanceTimersByTime(30000) the rendered value is 60 (advance inside
      act() from @testing-library/react).
   3. clamps at 0 (advance beyond the target -> '0', never negative).
   4. stop() halts the countdown (advance after stop -> value unchanged) and isRunning is false
      (render isRunning too, or assert via the component's behaviour).
   5. onComplete fires exactly once when the target is reached (vi.fn(), assert call count 1
      after crossing zero, and 0 before).
   6. start() twice does not double-count (two start() calls then advance 30000 -> 60, not 30).
  Make sure the string `vi.useFakeTimers()` literally appears in the file (AC-8 greps it).

FILE 6 — components/Countdown.test.tsx
  Read components/Countdown.tsx first for its real props (it wraps/uses useCountdown or takes
  seconds/remaining — assert what it actually renders). Tests: renders the formatted value it
  claims (mm:ss or seconds — read it); shows a zero/expired state; applies the className/status
  class it declares. Assert with textContent from a container query or getByTestId if the
  component has testids; otherwise match the visible text. >=3 assertions is fine.

FILE 7 — components/WaitlistCard.test.tsx
  Read WaitlistCardProps (line ~32 of components/WaitlistCard.tsx) and render with
  mockWaitlistEntry-derived props. Tests: name, queueNumber and partySize are rendered;
  waitMinutes/holdMinutes appear when provided; note renders when provided and is absent when
  omitted; the action buttons/callbacks the props declare (onSeat/onCall/onNoShow/onClick or
  whatever exists) fire the callback with the right argument (fireEvent.click + toHaveBeenCalled
  equivalent: assert mock.calls length and args with expect(fn).toHaveBeenCalledTimes(1)).
  Conditional styling per status if the component switches on it.

FILE 8 — components/TableCard.test.tsx
  Read TableCardProps (line ~26). Tests: label + capacity render; the occupant block renders
  queueNumber/partySize when an occupant exists and is absent when null/undefined; status-driven
  class or text differs between the statuses the component supports; onClick/onStatusChange
  callback fires with the table id/label (whatever it passes).

FILE 9 — components/EmptyState.test.tsx
  Props are { title, description, className? } (icon/emoji is internal). Tests: title text and
  description text render; className is appended to the root element (root.className contains
  the passed class); the built-in emoji branch renders an emoji element when no icon prop is
  passed (assert the emoji textContent is non-empty).

FILE 10 — components/StatusBadge.test.tsx
  Read the component's status prop union. Tests: renders a visible label for EVERY status in
  its union (loop over the status keys; assert non-empty textContent for each — that also
  drives coverage of the label map); the label text for at least two specific statuses matches
  the mapping declared in the source; the class for at least two statuses differs (read the
  class map from the source and assert root.className contains the expected fragment).

FILE 11 — components/ConfirmDialog.test.tsx
  Read ConfirmDialog's props ({ open, onClose, title, description?, variant?, confirmLabel?,
  cancelLabel?, onConfirm, onCancel? }). Tests (use render + screen + within):
   1. open=false renders nothing (container.textContent === '').
   2. open=true shows title and description text and role="dialog" (root has role or aria).
   3. default labels CONFIRM/CANCEL appear when confirmLabel/cancelLabel are omitted.
   4. custom confirmLabel/cancelLabel replace them.
   5. clicking confirm calls onConfirm once; clicking cancel calls onCancel once.
   6. variant="danger" gives the confirm button the danger styling (className contains the
      danger color fragment used in the source).

FILE 12 — layouts/StaffLayout.test.tsx
  StaffLayout renders <Outlet/> + header nav with logout (read the file). Render inside
  <MemoryRouter><Routes><Route path="/" element={<StaffLayout/>}><Route index element={<div>CHILD</div>}/></Route></Routes></MemoryRouter>.
  Tests: the outlet content renders (text CHILD present); the nav links for /staff/waitlist and
  /staff/tables are present as anchors (assert anchor text and getAttribute('href')); the
  logout button exists; clicking logout calls staffStore's clearToken/setToken (mock
  '@/stores/staffStore' with vi.mock if it is imported, or mock '@/api/staffStore' — READ which
  one StaffLayout imports and mock THAT one) and navigates (assert with a MemoryRouter
  initialEntries + a location probe component, or simply assert the store mock was called).

FILE 13 — pages/NotFoundPage.test.tsx
  Read pages/NotFoundPage.tsx. Tests: the 404 heading/heading text it renders is present; the
  "back home"/home link exists with href '/' (or whatever it declares — read the source and
  assert the real value).

ALSO REQUIRED (AC-2 greps that EVERY file under pages/ and layouts/ has a colocated .test file
  and that the four repaired ones are honest):
  - pages/public/BoardPage.test.tsx: it currently asserts on the real component? READ it. If it
    only checks that something rendered, add at least: branch name from the mocked API is shown,
    table cards appear for each mocked table, and the polling call repeats after
    vi.advanceTimersByTime(5000) with fake timers (BoardPage uses window.setInterval(load,5000)).
  - pages/staff/LoginPage.test.tsx: add a wrong-PIN case (API mock rejects -> error message text
    appears and no token is stored) and a correct-PIN case (token stored + navigate called).
    Mock the router's useNavigate with vi.mock('react-router-dom', async (orig) => ...).
  - stores/staffStore.test.ts: cover token set + clear + persistence if implemented (read the
    store; localStorage keys are read-only reads, do not write).
  - pages/public/JoinPage.test.tsx, LookupPage.test.tsx, StatusPage.test.tsx,
    pages/staff/WaitlistPage.test.tsx, TablesPage.test.tsx: they already have tests — only touch
    them if AC-2/AC-10 fails (AC-2 needs a *.test.tsx next to each page/layout file, and it is
    satisfied by StaffLayout.test.tsx + NotFoundPage.test.tsx which you are adding).
  NEVER delete assertions from an existing test file to make it pass; if an existing test fails
  after your vite.config change, fix the test honestly and report what you changed.

TARGET NUMBERS (measured today, at 627828a8)
  tests: 105 -> need >=100 (you are adding ~40-60, so fine)
  src/api/client.ts 27.17% -> >=70 statements; src/api/errors.ts 27.17% -> >=70
  src/components aggregate 31.61% -> >=70 (below-70 files today: Countdown, DevBadge, QrCode,
    SoundToggle, StatusBadge, TableCard, WaitlistCard — your new tests must lift the aggregate;
    if DevBadge/QrCode/SoundToggle still drag it below 70%, ADD tests for them too: they are
    small (DevBadge renders only under DEV; SoundToggle toggles a stored flag; QrCode renders an
    svg/canvas via qrcode.react's QRCodeSVG). Adding those three files is IN SCOPE and allowed.)
  useCountdown 5.66% -> covered by FILE 5.

VERIFY LOOP (run after each batch of files, always prefixed 'cd /home/te/tq/F-15 && '):
  timeout 600 npm --prefix frontend test -- --run                     (all green, >=100 tests)
  timeout 600 npm --prefix frontend run typecheck                     (Found 0 errors)
  timeout 600 npm --prefix frontend run build                         (built in)
  timeout 900 python3 /mnt/c/Users/tw097/Desktop/ai-dev-tools-zoomcamp/.tq-orchestrator/runacs.py _docs/issues/F-15.md   (green=12)
  timeout 600 npm --prefix frontend test -- --run --coverage --coverage.reporter=json-summary
     then read frontend/coverage/coverage-summary.json to check per-file pct BEFORE trusting AC-6/AC-7.
Commit + push after every 2-3 files (path-scoped git add, message 'test(F-15): ...').
