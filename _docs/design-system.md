# Design System

Version: 0.1.0
Last updated: 2026-09-10

This file states **how the front end is built**. It does not restate the visual
specification.

**`_docs/ui.md` is the single source of truth** for design tokens, typography,
the component inventory, page layouts, states, responsive rules, and
accessibility. This file points at it instead of duplicating it. If the two
disagree, `_docs/ui.md` wins and this file is corrected.

---

## 1. Stack

From `README.md` and `_docs/requirements.md#2-tech-stack`:

| Concern | Choice |
|---|---|
| UI library | React 18 with function components and hooks |
| Build tool / dev server | Vite |
| Language | TypeScript (`strict: true`) |
| Styling | Tailwind CSS utility classes |
| Component primitives | shadcn/ui |
| Server state | TanStack Query |
| Client state | Zustand |
| Toasts | Sonner (`Toaster` mounted in `frontend/src/main.tsx`) |
| Icons | `lucide-react` |
| QR code | `qrcode.react` |

There is **no server-side template layer** and **no CSS framework CDN** in this
project. Anything resembling `base.html`, Jinja templates, or Bootstrap 5 is a
leftover from an unrelated sample project and must not be reintroduced.

---

## 2. Where the rules live

| Topic | Source of truth |
|---|---|
| Design principles, colour tokens, typography, spacing and radius | `_docs/ui.md` sections 1-4 |
| Component inventory (shadcn/ui and custom), button sizes and states | `_docs/ui.md` section 5 |
| Per-page layout and behaviour | `_docs/ui.md` section 6 |
| Empty / loading / error states | `_docs/ui.md` sections 7-9 |
| Responsive breakpoints and layout rules | `_docs/ui.md` section 10 |
| Accessibility rules | `_docs/ui.md` section 11 |
| Motion, sounds, icons | `_docs/ui.md` sections 12-14 |
| Confirm dialogs and toasts | `_docs/ui.md` sections 15-16 |
| Custom component props | `_docs/ui.md` section 19 |
| Business rules behind the UI | `_docs/specs.md` |
| API shapes the UI consumes | `_docs/openapi.yaml` |

---

## 3. Wiring the tokens into Tailwind

Colour and font values are defined only in `_docs/ui.md`. They are registered
once, in `frontend/tailwind.config.js`, during F-02:

- Status colours (`WAITING`, `CALLED`, `SEATED`, `NO_SHOW`, `CANCELLED`, `DONE`)
  and table statuses (`AVAILABLE`, `OCCUPIED`, `CLEANING`) become theme colours,
  so components reference semantic names, never hex literals.
- The `Inter` family with `Noto Sans TC` fallback becomes the sans stack.
- Components then use utilities (`bg-called`, `text-primary`, `rounded-2xl`)
  rather than inline styles or hardcoded hex values.

Rule: **no hex colour literal appears in a `.tsx` file.** If a token is missing,
it is added to `_docs/ui.md` first, then to `tailwind.config.js`.

---

## 4. Component conventions

- Primitives come from shadcn/ui (`Button`, `Input`, `Label`, `Card`, `Dialog`,
  `Select`, `Badge`, `Table`, `Skeleton`, `Switch`, `Checkbox`, `Form`); the
  project-specific components listed in `_docs/ui.md` section 5 live in
  `frontend/src/components/`.
- One component per file, file named after the component, imported through the
  `@` alias.
- A component that appears in a page mock-up but not in `_docs/ui.md` section 5
  is not built: `_docs/ui.md` is extended by a docs issue first.
- Reusable props are documented in `_docs/ui.md` section 19.

---

## 5. State rendering

Every screen renders four states, defined in `_docs/ui.md` sections 7-9:

1. Loading: `LoadingSkeleton` with the variant named for the page.
2. Empty: `EmptyState` with icon, title, description, and action.
3. Error: the message mapped from the error code in `_docs/specs.md` section 11;
   unexpected failures surface through `ConnectionBanner` or a toast.
4. Data: the page body.

Server data is read through TanStack Query hooks keyed off
`frontend/src/api/queryKeys.ts`; mutations invalidate those keys. Auth token and
sound preference live in the Zustand `staffStore` and nowhere else.

---

## 6. Responsive and accessibility

Both are normative in `_docs/ui.md` and summarised here only so the constraint is
visible while coding:

- Guest pages are mobile-first and width-capped; staff pages are
  tablet/desktop-first. Breakpoints and per-page rules: `_docs/ui.md` section 10.
- Icon buttons carry `aria-label`, dialogs trap focus, status text is announced
  politely, contrast stays at or above 4.5:1: `_docs/ui.md` section 11.
- Sizing uses `rem`, and 200% browser zoom must not break the layout:
  `_docs/ui.md` section 3.

---

## 7. Copy rules

- All UI text is English. No CJK characters ship in user-visible strings.
- Date and time display as `2026-09-10 21:00`.
- Phone numbers display as Taiwan format (`09xx-xxx-xxx` / `02-xxxx-xxxx`).
- Copy for each page is specified in `_docs/ui.md` section 6; reproduce it rather
  than inventing new wording.

---

## 8. Theme

Light theme only in v1. Dark mode and i18n are non-goals; see `_docs/ui.md`
sections 17 and 18.

---

## 9. Related documents

- `_docs/ui.md` — the UI specification this file defers to
- `_docs/specs.md` — functional specification
- `_docs/openapi.yaml` — API contract
- `_docs/testing.md` — how UI behaviour is verified
- `_docs/plan.md` F-02, F-05, F-06 — the issues that scaffold and populate the
  front end
