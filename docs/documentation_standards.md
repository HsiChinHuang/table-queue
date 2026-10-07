# Documentation Standards

All documentation MUST follow this standard.

## Language Policy

Two tiers:

| Tier | Files | Language |
|---|---|---|
| **Agent I/O** | `docs/issues/*.md`, `docs/plan.md`, `docs/backlog.md`, `schemas/*.json`, `skills/**/*.md`, `AGENTS.md` | English only |
| **Human Setup** | `docs/coding_standards.md`, `docs/documentation_standards.md`, `docs/memory/readme.md`, `docs/memory/rules.md`, `docs/log/api_failures_rules.md` | English only |
| **User Input** | `docs/requirements.md` | Any language |
| **Runtime Status** | `docs/state/status.md`, `docs/state/questions.md`, `docs/log/*.md`, `docs/memory/index.md` | English only |

**Rule**: All files in this project use English, except `docs/requirements.md` which is provided by the user.

## File Naming

- All `snake_case`.
- Markdown extension `.md`.
- No uppercase.

## Markdown Format

### Headings

- Only `#` to `###`.
- `#` for document title only.
- `##` for main sections.
- `###` for subsections.
- `####` and deeper are forbidden.

### Lists

- Unordered: `-`.
- Ordered: `1.`, `2.`.
- `*` is forbidden.

### Tables

- Each column has at least 3 `-`.
- Alignment: left (`---`).
- Keep content short.

### Code Blocks

- Mark the language: ` ```python `.
- File content uses ` ```markdown `.
- Nested code blocks use 4 backticks for the outer block.

### Links

- Internal links use relative paths: `[text](../path/file.md)`.
- Absolute paths are forbidden.

### Images

- No images (plain text project).

## File-Specific Standards

### Issue Files (`docs/issues/*.md`)

Required sections:

- Frontmatter: `id`, `title`, `depends`, `platform_issue`
- `## Metadata`
- `## Goal`
- `## Context`
- `## Acceptance criteria`
- `## Verification commands`
- `## Test requirements`
- `## Implementation notes`
- `## Dependencies`
- `## Out of scope`
- `## Constraints`
- `## Definition of Done`

### Plan (`docs/plan.md`)

Structure:

- Tech stack
- Milestones (2–5)
- Issue blocks per milestone

### Backlog (`docs/backlog.md`)

Table:

    | ID | Title | Depends | Platform | Status |

### ADR (Architecture Decision Record)

If needed, place in `docs/adr/NNNN_<title>.md`:

- `# NNNN: <title>`
- `## Status`
- `## Context`
- `## Decision`
- `## Consequences`

## Comments

### Markdown Comments

Use HTML comments: `<!-- comment -->`.

### Code Comments

- Explain "why", not "what".
- In English.
- Avoid TODO. If necessary, attach issue ID: `# TODO(t42): ...`.

## Update Timing

| File | When updated |
|---|---|
| `docs/requirements.md` | By human |
| `docs/plan.md` | Definer: survey |
| `docs/backlog.md` | Definer / Orchestrator |
| `docs/issues/*.md` | Definer: groom / re_groom |
| `docs/coding_standards.md` | Rarely after init |
| `docs/documentation_standards.md` | Rarely after init |
| `docs/state/status.md` | Orchestrator every iteration |

## Forbidden

- No emojis.
- No full-width punctuation.
- No non-ASCII characters in code blocks.
- No HTML in Markdown (except comments).