---
name: hub-project-discovery
description: Use when refreshing or maintaining the local map of hub.workfront.com projects that renzler-related tasks should be filed into (task-logging routing for golden-thread cases, enterprise-context tenant issues, Workfront skill work, and eval-suite fixes), including scheduled/automated weekly runs of that refresh.
---

# Hub Project Discovery

## Overview

Maintains a local map of which `hub.workfront.com` project each category of
renzler/eval-related task should be filed into, plus fresh example
AI-Dev-US tasks from those projects to use as a naming/estimate/status
template. Refreshes known projects in place and appends any newly
discovered candidate projects for manual review — it never files tasks
itself and never auto-assigns a new project to a category.

## Output file

`/Users/sammefford/projects/hub/projects_for_tasks.md`

Overwrite each tracked project's section in place (refreshed fields +
new "Last refreshed" timestamp) — this is a maintained map, not an
append-only log. Only the "New candidates" section (see below) grows
over time, and only until a human resolves each entry.

## Tracked project Examples

| Category | Project | ID |
|---|---|---|
| 1. Enterprise-context benchmarking, Golden-thread cases | Run Eval Tests | `6a66359b0000042c21ac0f735a9237b8` |
| 2. Workfront skill for Claude and ao/CX Coworker | [E] Release Planning Solution Architect skill in Co-worker | `6a10e0d2000005ce1fce7e9cf8de7e70` |
| 3. Harness comparison | Renzler-Service | `6a8caaa80000700fdf61f747b995d4e4` |
| 4. Enterprise-context benchmarking | Build the Testing Framework That Proves Enterprise Context Works (1) | `6a66361d00000421ba3d40a1dbcecc52` |
| 5. Workfront MCP | 2026 Q3 Workfront API MCP Framework | `6a5fd75e000077a590cdda45b2e67bb0` |

If the output file's own project IDs ever diverge from this table (a
prior run added/removed a tracked project), treat the **file** as the
source of truth and update this table to match — this table is a
starting point, not an override.

## Steps

1. **Refresh known projects.** For each unique project ID:
   - Pull the current project object via `insights_find_workfront_data`
     or `context_get_project_context_first` (full fields, not just
     name/status).
   - Pull 2-4 current example tasks assigned to AI-Dev-US team or Sam Mefford
     on that project (filter by
     assignee + status equatesWith NEW/INP, or by project ID if you
     need any-assignee examples for naming convention).
   - Overwrite that project's section in the output file with the
     refreshed fields, example tasks, and a new
     `_Last refreshed: <ISO timestamp>_` line. Preserve the
     category-matching narrative text (confidence level, "why this
     project" reasoning) — only the field dump and example-task list
     are mechanically refreshed.

2. **Scan for new candidates.** Query `insights_find_workfront_data`
   for tasks assigned to Sam Mefford (or the AI-Dev-US team, if a team
   filter is available) with status `equatesWith` NEW/INP, grouped by
   project. For any project ID that appears here but is **not** in the
   tracked-projects table above, append it under a `## New candidates
   (needs review)` section at the end of the output file: project name
   + URL, 1-2 example tasks, and the date first seen. Do not guess
   which of the 5 categories it belongs to — that's a human call.
   - If a candidate already has an entry in "New candidates" from a
     prior run, refresh its example tasks in place rather than
     duplicating the entry.
   - If a human has since promoted a candidate into the main
     tracked-projects table (you'll see it there instead), remove it
     from "New candidates".

3. **No proactive notification.** Silently update the file, same as
   `sync-tasks` — this is a snapshot for the next session to read, not
   an alert.

## Quick reference

| Step | Tool |
|---|---|
| Full project field dump | `mcp__workfront-hub__insights_find_workfront_data` or `mcp__workfront-hub__context_get_project_context_first` |
| Example tasks by project/assignee | `mcp__workfront-hub__insights_find_workfront_data` |
| Status/enum lookup (if needed) | `mcp__workfront-hub__workflow_read_workflow_docs` |

## Common mistakes

- Re-running the full epic/view discovery process (the one-time search
  through the "Monthly Commit Meeting View") instead of using the
  tracked-projects table — that table exists so this skill never has
  to re-derive project IDs from scratch.
- Auto-assigning a newly discovered project to one of the 5 categories
  instead of appending it to "New candidates (needs review)".
- Appending to a project's section instead of overwriting it, leaving
  stale duplicate field dumps behind.
- Hand-building Workfront URLs instead of using the `url` field on
  returned objects.
