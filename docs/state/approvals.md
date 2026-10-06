# Approvals

Human writes approval lines here when `approval.mode != full-auto`.

## Format

    <action>:<id>: approved <timestamp>
    <action>:<id>: rejected <timestamp>
    <action>:<id>: consumed <timestamp>

## Examples

    merge:t42: approved 2026-10-05 14:30
    deps:add:requests: approved 2026-10-05 14:35
    delete:users/legacy.py: approved 2026-10-05 14:40
    ci:workflow_update: approved 2026-10-05 14:45
    reset:abc1234: approved 2026-10-05 15:00
    reset-confirm:abc1234: approved 2026-10-05 15:05
    reset-non-latest:abc1234: approved 2026-10-05 15:10
    config-change:slots.max:from=3,to=5: approved 2026-10-05 15:15
    force-merge:t42: approved 2026-10-05 15:20

## Active approvals

(none)

## Consumed approvals

Format: `<action>:<id>: consumed <timestamp>`

(none)

## Rejected approvals

Format: `<action>:<id>: rejected <timestamp>`

(none)