---
name: workfront
description: Use when ranking Workfront tasks/issues assigned to Sam by priority, deciding what to work on next, or generating a Workfront workload report. Scoped to hub.workfront.com only.
---

# Workfront Priority

Ranks Workfront tasks and issues assigned to Sam on **hub.workfront.com
only** (not the engineering or ai-dev instances), and recommends a next
action for each.

## Caching — read before any live lookup
- `references/hub-user-id.txt` — Sam's resolved hub.workfront.com user ID.
  Read this file first. Only call
  `mcp__workfront-hub__insights_get_current_user` again if the file is
  missing or a query using the cached ID fails unexpectedly.
- `references/docs-index/pyramid_summaries.md` — start here for any
  Workfront query-syntax question (status/priority enums, date filters,
  ordering). Only call `mcp__workfront-hub__workflow_read_workflow_docs`
  again if the index doesn't cover what's needed.

## Prioritization algorithm
See `references/prioritization.md` for the exact ranking order and
next-action rules — kept separate so it can be tweaked independently.

## Procedure
1. Read `references/hub-user-id.txt` for Sam's user ID.
2. Query `mcp__workfront-hub__insights_find_workfront_data` (or
   `planning_search_records`) for tasks and issues assigned to that user ID
   on hub.workfront.com, not yet complete.
3. Rank the results per `references/prioritization.md`.
4. For each item, write the recommended next action with a one-line reason.
5. Write the full report to
   `~/.claude/skills/workfront/reports/YYYY-MM-DD.md` (today's date;
   **overwrite** if it already exists), ranked list, each item showing its
   Workfront `url` deep link, priority, due date, and recommended action
   with reasoning. Give each item a stable anchor (e.g.
   `#task-<id-or-slug>`).
6. Reply in chat with a short summary: item count, how many overdue, and
   the report file path.

## Error handling
If a query fails after the cached user ID/docs don't resolve the issue
(e.g. real auth expiry), surface the error as a one-line note — do not
retry silently or fabricate results.
