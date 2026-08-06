# Workfront API Query Syntax — Sorting (orderBy)
**Presenter/Author:** Workfront (`mcp__workfront-hub__workflow_read_workflow_docs`, `workfront://reference/query-syntax`), with workfront-specific usage notes added at cache time
**Format:** MD
**Source file:** order-by.md
**Topic:** How to sort Workfront API query results using `orderBy`, and how to apply it to rank tasks/issues by due date within a priority tier.

## Abstract
Short reference: the `orderBy` parameter takes a `fieldName` and an `order` of `asc` or `desc`. The doc adds a usage note tying this directly to the workfront skill's ranking algorithm — sort ascending on the due-date field to surface soonest-due items first within each priority tier.

## Key Points
- `orderBy` = `{ fieldName, order }`; `order` is `asc` or `desc`.
- For "soonest due date first within a tier," sort `asc` on the due-date field.
- Sorting should be applied after filtering (status not-complete, assignee = Sam, optionally overdue) — see `date-filters.md` for the filter side and `status-priority-fields.md` for the enum values used in those filters.

## Conclusions / Decisions / Recommendations
workfront's three-step rank (overdue first → priority tier → soonest due date) is implemented as: (1) partition results into overdue vs. not-overdue using a `lte $$TODAY` due-date filter, (2) within each partition, group/sort by numeric priority descending, (3) within each priority group, `orderBy` due-date ascending.

## Open Questions / Outstanding Items
The raw doc doesn't specify whether multi-key `orderBy` (priority then due date in one call) is supported natively vs. requiring client-side secondary sort — the workfront skill should sort client-side by priority-then-due-date after fetching if the API only supports a single `orderBy` key, to be safe.

## Key People & Projects
None (reference doc only).

## Notes
This raw-doc file is a short excerpt (sorting section only) pulled from the same `query-syntax` doc fetch as `date-filters.md`; no extraction limits.
