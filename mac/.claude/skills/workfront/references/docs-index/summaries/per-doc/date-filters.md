# Workfront API Query Syntax — Filter Modifiers and Date Ranges
**Presenter/Author:** Workfront (`mcp__workfront-hub__workflow_read_workflow_docs`, `workfront://reference/query-syntax`)
**Format:** MD
**Source file:** date-filters.md
**Topic:** How to build filter conditions against the Workfront API, with emphasis on the `_Mod` comparison-operator suffix and the `_Range` pair used for `between` queries — the mechanism needed to find overdue/upcoming tasks by due date.

## Abstract
Documents the `_Mod` suffix pattern (append to any field name to change comparison semantics from the default `eq`) and the paired `_Range` suffix used specifically with the `between` modifier. Also covers logical grouping (`OR:`/`AND:`/`EXISTS:`), related-field colon-notation queries, custom (`DE:`) fields, and pagination.

## Key Points
- Default comparison is always `eq`; every other comparison requires `<field>_Mod: "<modifier>"`.
- For due-date filtering: `lte` with `$$TODAY` finds overdue items, e.g. `{ "plannedCompletionDate": "$$TODAY", "plannedCompletionDate_Mod": "lte" }` (adapt field name to the actual due-date field on tasks/issues).
- `between` requires both `_Mod: "between"` and a `_Range` key holding the upper bound, e.g. `{ "entryDate": "2024-01-01", "entryDate_Mod": "between", "entryDate_Range": "2024-12-31" }`.
- `in`/`notin` take a JSON array as the field value plus the matching `_Mod`.
- Status-not-complete filtering uses `notin` against the status enum values documented in `status-priority-fields.md`.
- Related-object filters use colon notation (`assignedTo:emailAddr`), useful for filtering tasks/issues by assignee without a separate join.
- Custom fields are prefixed `DE:`.
- Pagination: default limit 100, max 200; use `offset` to page.

## Conclusions / Decisions / Recommendations
For workfront's "assigned to Sam, not yet complete, ranked by overdue-ness" query: combine an assignee-ID equality filter, a status `notin`-complete filter, and (optionally) a due-date `lte $$TODAY` filter to isolate the overdue subset before applying the full priority-tier + due-date sort from `order-by.md`.

## Open Questions / Outstanding Items
None flagged in the source doc.

## Key People & Projects
None (reference doc only).

## Notes
No extraction limits; doc is a clean markdown reference with example JSON filter fragments.
