---
name: sync-tasks
description: Use when refreshing or generating a local brief of the user's open Workfront tasks from hub.workfront.com, including scheduled/automated runs of that refresh.
---

# Sync Tasks

## Overview

Pulls the user's open tasks from the `workfront-hub` Workfront instance
(hub.workfront.com) and writes them to a local brief file, overwriting it
each run so the file always reflects current state.

## Output file

`/Users/sammefford/projects/hub/claude_automated/workfront-tasks-brief.md`

## Steps

1. Get the current user via `mcp__workfront-hub__insights_get_current_user` → `user_id`.
2. Call `mcp__workfront-hub__insights_find_workfront_data` with:
   - `field_paths`: `task.task_name`, `task.task_status`,
     `task.task_plannedCompletionDate` (sort asc, index 0),
     `task.task_project.project.project_name`
   - `condition`: AND of
     - `{fieldId: "task.task_assignedToID", operator: "eq", values: [user_id]}`
     - `{fieldId: "task.task_status", operator: "equatesWith", values: ["NEW", "INP"]}`
       (this maps every status whose category is New or In Progress —
       covers custom statuses too, not just the literal codes NEW/INP)
   - `limit: 100`
   This is the verified working query — don't re-derive field paths from
   scratch each run.
3. Results already come back with markdown links embedded in the
   `task.task_name` and `task.task_project...project_name` values
   (`[label](url)`) — use them as-is, don't strip or rebuild them.
4. Sort by `plannedCompletionDate` ascending (already sorted by the query);
   tasks with an empty date string go last.
5. Write/overwrite the output file as markdown:
   - H1 title `# Open Workfront Tasks` plus a `_Last synced: <ISO timestamp>_` line.
   - One bullet per task: `- <task name link> — <project name link> — due <date or "no due date">`.
   - If there are zero rows (`totalCount: 0`), write `No open tasks.` under the title instead of a list.

## Quick reference

| Step | Tool |
|---|---|
| Resolve current user | `mcp__workfront-hub__insights_get_current_user` |
| Query open tasks | `mcp__workfront-hub__insights_find_workfront_data` |
| Enum/status lookup (if needed) | `mcp__workfront-hub__workflow_read_workflow_docs` |

## Common mistakes

- Appending to the brief file instead of overwriting it — always overwrite, this is a snapshot not a log.
- Hand-building Workfront URLs instead of using the `url` field on returned objects.
- Skipping `workflow_read_workflow_docs` when filtering by status — status values are enums, not free text.
