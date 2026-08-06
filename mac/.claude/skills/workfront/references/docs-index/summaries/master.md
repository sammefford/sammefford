# Workfront Docs (workfront caching) — Master Summary
Generated: 2026-08-06

## What this is
Three reference docs fetched from `mcp__workfront-hub__workflow_read_workflow_docs` on hub.workfront.com, cached so the `workfront` skill doesn't need to re-fetch Workfront query-syntax documentation on every run. They cover the three things the skill's prioritization query depends on: status/priority enum values, date-range filter syntax (`_Mod`/`_Range`), and result ordering (`orderBy`). All three came from two underlying doc URIs (`workfront://reference/status-codes` and `workfront://reference/query-syntax`) fetched on 2026-08-06.

## Document index
| File | Author/Presenter | Format | Topic | Abstract |
|------|-------------------|--------|-------|----------|
| [status-priority-fields.md](per-doc/status-priority-fields.md) | Workfront (`workfront://reference/status-codes`) | MD | Status/priority/severity enum values | Enum lookup table for project/task/issue statuses, priority (0–4), issue severity (1–5), and issue types; needed to build "not yet complete" and priority-tier filters. |
| [date-filters.md](per-doc/date-filters.md) | Workfront (`workfront://reference/query-syntax`) | MD | `_Mod`/`_Range` filter syntax | Documents the `_Mod` comparison-operator suffix and paired `_Range` for `between` queries, plus logical grouping, related-field colon notation, custom fields, and pagination; needed to filter tasks/issues by assignee, status, and due date. |
| [order-by.md](per-doc/order-by.md) | Workfront (`workfront://reference/query-syntax`) | MD | `orderBy` sorting | Short reference on the `orderBy` parameter (`fieldName` + `asc`/`desc`), with usage notes tying it to workfront's overdue → priority-tier → due-date ranking. |

## Cross-cutting themes
- All three docs feed directly into one query: tasks/issues assigned to Sam, not yet complete, ranked overdue-first then by priority tier then by soonest due date.
- The enum values in `status-priority-fields.md` are the literal string/numeric values plugged into the filter conditions built with the syntax in `date-filters.md`.
- Sorting (`order-by.md`) is applied after filtering, and may need to be done client-side for the compound priority-then-due-date sort since the API's `orderBy` may only support a single key per call.

## Key entities referenced
| Name | Description | Related doc(s) |
|------|-------------|-----------------|
| `status` / `status_Mod` | Field + modifier used to exclude complete/closed items | status-priority-fields.md, date-filters.md |
| `priority` | Numeric 0–4 field, Urgent=4 down to None=0 | status-priority-fields.md |
| `_Range` | Paired suffix with `_Mod: "between"` for date-range queries | date-filters.md |
| `$$TODAY` | Special value for "today" in date comparisons (e.g. overdue check) | date-filters.md |
| `orderBy` | Sort parameter, `{fieldName, order}` | order-by.md |

## Action items & open questions
- Open question (from order-by.md): whether the API supports multi-key `orderBy` (priority then due date) in one call, or whether the skill must fetch then sort client-side. Treat as "sort client-side" until proven otherwise.
- No other open items — these are stable reference docs, not living design docs.
