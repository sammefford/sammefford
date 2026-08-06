# Workfront API Query Syntax — Sorting (orderBy)

Source: `mcp__workfront-hub__workflow_read_workflow_docs` — `workfront://reference/query-syntax`
(sorting section extracted from the full query-syntax doc; see `date-filters.md` for the
filter-modifier and range sections from the same fetch)

## Sorting

Use the `orderBy` parameter with `fieldName` and `order` (`asc` or `desc`).

Notes for this skill's use case (ranking tasks/issues by due date within a priority tier):
- Sort ascending (`asc`) on the due-date field to get soonest-due-first within a tier.
- Combine with a status/priority filter (see `status-priority-fields.md` for enum values)
  and a date filter (see `date-filters.md` for `_Mod`/`_Range` syntax) to scope the query
  before sorting.
