# Design System

## Overview

The UI uses Bootstrap 5 for styling and layout.

## Framework

- **Bootstrap 5** via CDN in `base.html`.
- Templates use Bootstrap grid, cards, badges, and navbar components.

## Template Structure

- `base.html` — Base template with Bootstrap 5 CDN, navbar, and block definitions (`title`, `extra_css`, `content`, `extra_js`).
- `chore_card.html` — Reusable partial for displaying a single chore assignment.
- `notification_list.html` — Partial for rendering notifications.
- `dashboard.html` — Main dashboard categorizing assignments into Today, Upcoming, and Overdue cards.
- `one_time_form.html` — Form for creating one-time chores with name, category, difficulty, and assignee fields.
- `fairness_stats.html` — Point breakdown by partner with history table and running total.
- `assignment_list.html` — Paginated list of all assignments with status filters.
- `notification_list.html` — Full-page notification viewer with mark-all-read and dismiss actions.
- `household_settings.html` — Editable household settings form (name, default interval, invite code).

## Static Files

- Static files are served from `static/` directories within apps.
