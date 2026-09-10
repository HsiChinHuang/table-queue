# TableQueue — UI Guide

Version: 0.1.0
Last updated: 2026-09-10

---

## 1. Design Principles

- **Dual style**: guest side is warm and spacious; staff side is dense and color-coded.
- **Guest side**: mobile-first, large text, rounded corners, soft shadows.
- **Staff side**: tablet/desktop-first, high information density, clear status colors.
- **Shared tokens**: Tailwind + shadcn/ui, same color tokens, different layouts.
- **All UI text is in English.**
- **Date format**: `2026-09-10 21:00` (ISO + 24h).
- **Phone format**: Taiwan `09xx-xxx-xxx` / `02-xxxx-xxxx`.
- **No dark mode in v1.** Use `dark:` reserved classes.

---

## 2. Color Tokens

Reused values: the token for `CALLED` is shared by `OCCUPIED`; the token for `SEATED` is shared by `AVAILABLE`. This is intentional re-use of one warm/orange "act now" hue and one green "ready" hue across two namespaces.

### Base
| Token | Value | Usage |
|---|---|---|
| `bg-guest` | `#FFFBF5` | Guest layout background |
| `bg-staff` | `#F8FAFC` | Staff layout background |
| `text-primary` | `#1E293B` | Main text |
| `text-secondary` | `#64748B` | Secondary text |
| `border-default` | `#E2E8F0` | Borders |
| `primary` | `#EA580C` | Primary action |
| `primary-hover` | `#C2410C` | Primary hover |

### Waitlist status
| Status | Value |
|---|---|
| `WAITING` | `#3B82F6` |
| `CALLED` | `#F97316` |
| `SEATED` | `#22C55E` |
| `NO_SHOW` | `#EF4444` |
| `CANCELLED` | `#94A3B8` |
| `DONE` | `#15803D` |

### Table status
| Status | Value |
|---|---|
| `AVAILABLE` | `#22C55E` |
| `OCCUPIED` | `#F97316` |
| `CLEANING` | `#A855F7` |

### Semantic
| Token | Value |
|---|---|
| `success` | `#16A34A` |
| `warning` | `#F59E0B` |
| `error` | `#DC2626` |
| `info` | `#0EA5E9` |

---

## 3. Typography

- Font family: `Inter`, fallback `Noto Sans TC`, `system-ui`, `sans-serif`.
- Font display: `swap`.
- Use `rem` not `px`.
- Browser zoom 200% must not break layout.

| Element | Size |
|---|---|
| Guest status number | `text-5xl` |
| Guest page title | `text-2xl` |
| Guest body | `text-base` |
| Staff stat number | `text-3xl` |
| Staff card title | `text-base` |
| Staff body | `text-sm` |
| Staff meta | `text-xs` |

---

## 4. Spacing and Radius

- Page padding: `p-4` mobile, `p-6` desktop.
- Card gap: `gap-4`.
- Form field spacing: `space-y-4`.
- Section spacing: `space-y-6`.

| Element | Radius |
|---|---|
| Guest card | `rounded-2xl` |
| Staff card | `rounded-xl` |
| Staff section | `rounded-lg` |
| Button | `rounded-lg` |
| Badge | `rounded-full` |
| Input | `rounded-lg` |

- Card shadow: `shadow-sm`.
- Modal shadow: `shadow-lg`.
- No heavy shadows.

---

## 5. Components

### shadcn/ui components
`Button`, `Input`, `Label`, `Card`, `Dialog`, `Select`, `Badge`, `Table`, `Toast` (Sonner), `Skeleton`, `Switch`, `Checkbox`, `Form`.

### Custom components
| Component | Purpose |
|---|---|
| `WaitlistCard` | One waitlist entry in staff list |
| `TableCard` | One table in staff table map |
| `StatusBadge` | Colored badge for status |
| `Countdown` | `mm:ss` countdown for `CALLED` |
| `EmptyState` | Icon + title + description + action |
| `LoadingSkeleton` | Variants: `card`, `list`, `form`, `board` |
| `ConfirmDialog` | Confirmation dialog with variant |
| `ConnectionBanner` | Shows connection lost / updated |
| `SoundToggle` | Toggle sound on guest status page |
| `QrCode` | QR code for join URL |
| `DevBadge` | `DEV` badge in development |

### Button sizes
| Context | Height |
|---|---|
| Guest primary | `h-12` |
| Staff primary | `h-10` |
| Card action | `h-9` |

### Button states
- Disabled: `disabled:opacity-50 disabled:cursor-not-allowed`.
- Loading: disabled + spinner icon, keep label.
- Hover: `hover:bg-...`.
- Focus: `focus:ring-2 focus:ring-offset-2`.

### Transition
- Status change: `transition-colors duration-200`.
- Button hover: `transition-colors`.
- Never use `transition-all`.
- Respect `motion-reduce:`.

---

## 6. Pages

### 6.1 `/join` — Join Page
- Mobile-first, centered `max-w-md`.
- Shows restaurant name, waitlist status, hours.
- If `is_waitlist_open=false`, show closed message and hide form.
- Form fields: Name, Phone, Party size, Note (optional).
- Submit button: `Join Waitlist`.
- Validation on blur, re-validate on change.
- Error messages below fields.
- Success: navigate to `/status/{queueNumber}?token={statusToken}`.
- Duplicate phone: show `This phone number is already on the waitlist.` + `View Status` button.

### 6.2 `/status/:queueNumber` — Status Page
- Mobile-first, centered `max-w-lg`.
- If no `token` in query, show last-3-digits input form.
- Shows progress bar: `Waiting → Called → Seated`.
- Shows queue number in `text-5xl`.
- Shows `N groups ahead` and `Estimated wait: X min`.
- `WAITING`: blue, `Cancel` button.
- `CALLED`: orange background, countdown `mm:ss`, vibration, sound, `Cancel` button (confirm).
- `SEATED`: green, `You're seated. Enjoy your meal!`.
- `NO_SHOW`: red, `Restore` not available for guest.
- `CANCELLED`: grey, `Join Again` button.
- Polls every 5 seconds.
- Refetch on window focus.
- Refetch immediately when countdown reaches 0.
- Sound toggle in top-right.

### 6.3 `/lookup` — Lookup Page
- Mobile-first, centered `max-w-md`.
- Fields: Queue number, Last 3 digits of phone.
- Submit: `Look Up Status`.
- Success: navigate to `/status/{queueNumber}?token={statusToken}`.
- Failure: `No matching waitlist entry found.`

### 6.4 `/board/:branchId` — Public Board
- Read-only, no auth.
- Mobile: single column; desktop: two columns (left: now serving, right: QR code).
- Shows restaurant name, branch name, hours.
- If `is_waitlist_open=false`, show `Waitlist is currently closed.`
- Large `Now Serving: A012` text.
- `Next up: A013`.
- `Recent calls: A011, A010` (max 3).
- `Waiting: 5`.
- QR code: `Scan to join the waitlist`.
- Polls every 5 seconds.
- Shows only queue number and party size. Never names or phones.

### 6.5 `/staff/login` — Login Page
- Centered `max-w-sm`.
- Single PIN input (`type=password`, `inputMode=numeric`).
- `Remember me` checkbox (default checked).
- `Login` button.
- Error: `Invalid PIN.`
- On success: store token, navigate to `/staff/waitlist`.
- If already logged in, redirect to `/staff/waitlist`.

### 6.6 `/staff/waitlist` — Waitlist Page
- Staff layout.
- Top: stats cards (`Waiting`, `Called`, `Seated`, `Available Tables`, `Occupied`, `Cleaning`, `No-show today`, `Cancelled today`, `Seated today`, `Avg wait today`).
- Search box: name or phone last 3 digits.
- Status filter: `Active` / `Closed` / `All`.
- Party size filter.
- `Pause Waitlist` switch.
- `Close Day` button.
- Waitlist list: cards sorted by `sort_order`.
- Card actions: `Call`, `Seat`, `No-show`, `Restore`, `Revert`, `Cancel`, `Edit`.
- `CALLED` cards show countdown.
- Drag to reorder (or up/down buttons in v1).
- Collapsible `Closed today` section.
- `Last updated: HH:MM:SS`.
- Polls every 3 seconds.

### 6.7 `/staff/tables` — Tables Page
- Staff layout.
- Grid: `grid-cols-2 md:grid-cols-3 lg:grid-cols-4`.
- Each card: label, capacity, status color.
- `AVAILABLE` → click to mark `CLEANING`.
- `CLEANING` → click to mark `AVAILABLE`.
- `OCCUPIED` → shows `A012 · 4 pax · 25 min`, `Release Table` button.
- Empty state: `No tables yet. Add tables in Settings.`
- Polls every 5 seconds.

### 6.8 `/admin/settings` — Settings Page
- Staff layout, `max-w-4xl`.
- Sections:
  1. **Store Info**: name, address, phone, open time, close time.
  2. **Waitlist Settings**: hold minutes, avg seat minutes, queue prefix, waitlist open switch.
  3. **Tables**: list with edit/delete, add table form.
  4. **Notifications & Sound**: templates, sound default.
  5. **Danger Zone**: change PIN, reset data (dev only).
- Each section has its own `Save` button.
- Show range hints: `hold_minutes 5–15`, `avg_seat_minutes 5–60`.

### 6.9 `*` — Not Found Page
- `Page not found.`
- `Go home` button → `/join?branch=1`.

---

## 7. Empty States

| Page | Message |
|---|---|
| Waitlist | `No one is waiting right now.` |
| Tables | `No tables yet. Add tables in Settings.` |
| Board | `No one has been called yet.` |
| Status | `We couldn't find your waitlist entry.` |
| Lookup | `No matching waitlist entry found.` |
| Settings | `No templates configured.` |

- Exception: Join, Login and Not Found have no empty state; an empty state is not applicable to a PIN-only form or a 404 page (design-system.md:90 four-state rule covers the six data pages).

---

## 8. Loading States

- Always use skeletons, never spinners for page-level loading.
- List: 3–5 card skeletons.
- Board: card skeleton.
- Settings: form field skeleton.
- Status: centered large text skeleton.

---

## 9. Error States

- Full page: `Something went wrong.` + `Reload`.
- Inline: toast + inline message.
- Form: red text below field.
- Network: top banner `Connection lost. Retrying...`.
- Recovery: `Updated just now` for 3 seconds.

---

## 10. Responsive Breakpoints

Tailwind defaults:
- `sm`: 640px
- `md`: 768px
- `lg`: 1024px
- `xl`: 1280px

Layout rules:
- Guest pages: `max-w-md` or `max-w-lg`, centered.
- Staff waitlist: single column on mobile, two columns on `lg`.
- Table map: `grid-cols-2 md:grid-cols-3 lg:grid-cols-4`.
- Settings: single column on mobile, `max-w-4xl` on desktop.
- Both orientations supported.

---

## 11. Accessibility

- All icon buttons have `aria-label`.
- Modal focus trap; close returns focus to trigger.
- `StatusBadge` has `aria-live="polite"`.
- `Countdown` has `aria-live="off"`.
- Color contrast ≥ 4.5:1.
- Never use color alone to convey status; always include text.
- Keyboard navigation supported.
- Respect `prefers-reduced-motion`.

---

## 12. Motion

- `transition-colors duration-200` for status changes.
- `transition-colors` for button hover.
- Never `transition-all`.
- Disable animation under `motion-reduce:`.
- No animated page transitions in v1.

---

## 13. Sounds

- Web Audio API beep.
- Frequency: 880Hz.
- Duration: 0.3s.
- Requires user interaction first.
- Show `Tap to enable sound` banner if not yet enabled.
- Guest status page: sound on `CALLED`.
- Sound toggle stored in `staffStore.soundEnabled`.

---

## 14. Icons

Use `lucide-react`:
`Users`, `Clock`, `Check`, `X`, `AlertTriangle`, `Table`, `Settings`, `LogOut`, `Search`, `Filter`, `ChevronDown`, `ChevronUp`, `Volume2`, `VolumeX`, `QrCode`, `RefreshCw`, `Plus`, `Trash2`, `Edit`, `Phone`, `MapPin`, `Play`, `RotateCcw`, `Bell`, `BellOff`.

---

## 15. Confirm Dialogs

| Action | Title | Variant |
|---|---|---|
| Cancel | `Cancel this waitlist entry?` | danger |
| No-show | `Mark this guest as no-show?` | danger |
| Revert | `Revert this call?` | default |
| Release Table | `Release this table?` | default |
| Delete Table | `Delete this table? This cannot be undone.` | danger |
| Close Day | `Close the day? All active entries will be closed.` | danger |
| Reset Data | `Reset all data? Type RESET to confirm.` | danger |
| Change PIN | `Change staff PIN?` | default |

---

## 16. Toast

- Position: top-right.
- Success: 3s.
- Error: 5s.
- Warning: 5s.
- Dismissible.
- Use `sonner` with `richColors` and `closeButton`.

---

## 17. Dark Mode (non-goal)

- v1 does not support dark mode.
- Use `dark:` reserved classes only.
- No toggle UI.

---

## 18. i18n (non-goal)

- v1 is English-only.
- Strings centralized in `src/lib/strings.ts`.
- No `i18next` in v1.

---

## 19. Component Details

### WaitlistCard
- Row 1: `A001` + `StatusBadge`.
- Row 2: `John Smith · 4 pax`.
- Row 3: `Waiting 12 min` or `Called 2 min ago`.
- Row 4: note (if any).
- Actions on the right or below.

### TableCard
- Row 1: `A1` + status color block.
- Row 2: `2 pax`.
- Row 3: `Available` or `Occupied · A012 · 25 min`.
- Click to toggle or release.

### StatusBadge
- `WAITING`: blue, `Waiting`.
- `CALLED`: orange, `Called`.
- `SEATED`: green, `Seated`.
- `NO_SHOW`: red, `No-show`.
- `CANCELLED`: grey, `Cancelled`.
- `DONE`: dark green, `Done`.

### Countdown
- > 60s: `09:59`.
- < 60s: `00:59`.
- Zero: `00:00` in red.
- `aria-live="off"`.

### ConnectionBanner
- Show after 3 consecutive failures: `Connection lost. Retrying...`.
- On recovery: `Updated just now` for 3 seconds.
- Does not block interaction.

### EmptyState
- `icon`, `title`, `description`, `action` (optional).

### LoadingSkeleton
- `variant`: `card` | `list` | `form` | `board`.
- `count`: number.

### ConfirmDialog
- `title`, `description`, `confirmLabel`, `cancelLabel`, `variant`, `onConfirm`, `onCancel`.

### QrCode
- `value`, `size=200`, `level=M`, `bgColor=#FFFFFF`, `fgColor=#1E293B` (exception: QR encoder takes literal hex strings, not Tailwind classes).

### SoundToggle
- Reads `staffStore.soundEnabled`.
- Toggle plays beep on enable.
- Persists to localStorage.

### DevBadge
- Fixed top-right.
- `bg-yellow-400 text-black text-xs px-2 py-1 rounded` (exception: no token defined for badge yellow).
- Only when `import.meta.env.DEV`.