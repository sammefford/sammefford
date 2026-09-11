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

**Keep this file clean of exclusion/outdated language.** It's read by
other sessions who just need "which project do I file this under" —
don't distract them with "EXCLUDED", "no longer valid", drift notes
about a project that's been dropped, strikethrough entries, etc. All
of that bookkeeping (why a project was rejected, when, reopening-risk
reasoning) belongs in **this SKILL.md's "Excluded projects" table**
only. When a tracked project gets demoted per the reopening-risk rule
(see Validity criteria), remove its section from the output file
entirely (or fold any still-useful task links into a surviving
section) rather than marking it excluded in place — the output file
should only ever show the projects currently believed valid, described
plainly.

## Tracked project Examples

| Category | Project | ID |
|---|---|---|
| 1. Evaluate Enterprise Context effectiveness | [Enterprise Context] Add context tests, tools, and observability into MCP Evals | `6a98622000005f8a97c7598457042d93` |
| 2. Workfront skill for Claude and ao/CX Coworker | [E] Release Planning Solution Architect skill in Co-worker | `6a10e0d2000005ce1fce7e9cf8de7e70` |
| 3. Renzler-specific Harness comparison | Renzler-Service | `6a8caaa80000700fdf61f747b995d4e4` |
| 4. Unknown | Sam Mefford's Backlog | `6a9b2f4d0000102f536d55cd05aded57` |

Category 1 (Run Eval Tests) was removed from this table on 2026-09-08 —
see **Excluded projects** below, it flipped to Complete with a passed
Planned Completion Date and must not be used again.

If the output file's own project IDs ever diverge from this table (a
prior run added/removed a tracked project), treat the **file** as the
source of truth and update this table to match — this table is a
starting point, not an override.

## Excluded projects (never resurface)

These were suggested by a past run and rejected by Sam for a durable
reason — do not re-add them to "New candidates" even if a matching
task turns up again. If a scan would otherwise surface one of these,
skip it silently.

| Project | ID | Why excluded |
|---|---|---|
| Sam Mefford's Tasks | `69f15acc000005c6a21238eb524371e7` | Different Workfront workspace — Sam cannot move tasks to/from it. |
| [AI] Security Operations 2026-H2 | `6a0b569a000666ac8a4be4c8d1be326d` | Done; was never a project Sam should file new tasks against. |
| Build the Testing Framework That Proves Enterprise Context Works (1) | `6a66361d00000421ba3d40a1dbcecc52` | Passed Planned Completion Date; only had one stray task pointing at it, no current epic/monthly-commit backing it. |
| 2026 Q3 Workfront API MCP Framework | `6a5fd75e000077a590cdda45b2e67bb0` | Only had one stray task pointing at it, no current epic/monthly-commit backing it. |
| MCP Regressions | `6a714074000005e6bbe271687f110a23` | Current status and AI Dev US product group, but Planned Completion Date (8/30/26) has passed — fails validity criterion 2. |
| Run Eval Tests | `6a66359b0000042c21ac0f735a9237b8` | Flipped to Complete (CPL) with Planned Completion Date 9/4/26, now passed (as of 2026-09-08 check) — **reopening risk**: filing a new task here would reopen this project and, by rollup, reopen its parent epic. Formerly the primary tracked project for categories 1/2/5; see "[Enterprise Context] Add context tests, tools, and observability into MCP Evals" (`6a98622000005f8a97c7598457042d93`) as the still-Current sibling epic project — promoting it into the tracked table is a human call. |

**Correction (2026-09-08):** "Sam Mefford's Backlog" (`6a9b2f4d0000102f536d55cd05aded57`)
was previously listed here as excluded for a workspace mismatch — that was
wrong. Sam confirmed it's usable; see **Fallback project** below. It is
explicitly NOT the same project as "Sam Mefford's Tasks" (`69f15acc...`,
still excluded above), which really is in a different, unusable workspace.

## Fallback project

If none of the tracked categories or validated "New candidates" fit
and a task genuinely needs somewhere to go, default to **Sam Mefford's
Backlog** — `6a9b2f4d0000102f536d55cd05aded57`
(https://experience.adobe.com/#/@adobeinternalworkfront/so:hub-Hub/workfront/project/6a9b2f4d0000102f536d55cd05aded57/tasks).
This is a per-Sam fallback, not a category match — don't cite it as
the answer to "which category does X belong to," just as the default
when the routing genuinely can't tell.

## Validity criteria

The whole point of this skill is to find **current** projects that
trace back to **current** epics under **current** monthly commits —
not just any project that happens to have a task with a matching
bracket tag. A task landing on a project is weak evidence; a project
is only a real candidate (for the tracked table *or* "New candidates")
if it passes ALL of these:

1. **Project status is current.** Status must be `CUR` (or otherwise
   active) — exclude `CPL` (Complete), `CAN`/`DE` (Cancelled/Dead), or
   any terminal status. **Reopening risk**: a Workfront project rolls
   up to its parent Epic — filing a *new* task against a Complete
   project reopens that project, and by rollup, incorrectly reopens
   the Epic it belongs to. Treat `CPL` + a passed Planned Completion
   Date as a hard, permanent exclusion, never a soft/temporary one.
2. **Planned Completion Date has not passed.** If the project has a
   Planned Completion Date and it's in the past relative to today,
   exclude it — a passed completion date means the project is done in
   practice even if status hasn't been updated. This check matters
   most in combination with criterion 1: `CPL` status *and* a passed
   Planned Completion Date together is the exact reopening-risk
   condition — exclude permanently, don't wait for both independently.
3. **Same workspace as the tracked projects.** The project must live
   in the same Workfront workspace/group as the existing tracked
   projects (Run Eval Tests / the Planning skill project / Renzler-
   Service) — not a personal catch-all project (e.g. "<Name>'s Tasks")
   or a project in a workspace Sam can't move tasks to/from. When in
   doubt, compare the candidate's `group`/`portfolio` field against a
   known-good tracked project's; if they don't match, exclude it.
4. **Traces to a current epic under a current monthly commit.** Confirm
   the project is the target (via `recordExternalOptions`) of an Epic
   that itself sits under a currently-active Monthly Commit row in the
   "AI Dev US" Monthly Commit Meeting View (`V6a611a2b6b18dfd9700bc181`,
   record type `Rt6a4ec0aecb670e86f2633435`, workspace
   `Ws673bb145b454935a7c749f04`) — not a stale/past-commit epic. A
   project reached only through "a task happens to be assigned here"
   with no live epic/monthly-commit link is not a valid candidate; put
   it in "Excluded projects" instead of "New candidates" once you've
   checked and it fails this test, so it doesn't get re-suggested.

A candidate that fails criteria 1-3 can be checked and rejected without
touching the Monthly Commit View. Criterion 4 only needs the epic
traversal for candidates that otherwise look plausible — don't re-run
the full one-time view discovery for every scan (see Common mistakes),
just check whether the specific candidate project ID appears as a
target among current epics/commits.

## Steps

1. **Refresh known projects.** For each unique project ID:
   - Pull the current project object via `insights_find_workfront_data`
     or `context_get_project_context_first` (full fields, not just
     name/status).
   - **Re-vet for reopening risk before refreshing in place.** Check
     the pulled status + Planned Completion Date against Validity
     criteria 1-2. If a *tracked* project has flipped to `CPL`
     (Complete) with a Planned Completion Date that has now passed,
     do NOT just refresh its section as usual — instead:
     a. Move it from the tracked-projects table to **Excluded
        projects** in this file, with a one-line reason citing the
        reopening risk (project rolls up to its parent Epic; a new
        task would reopen both).
     b. In the output file, remove that project's section entirely
        (don't mark it excluded in place — see "Keep this file clean"
        above). If any of its still-open tasks are worth preserving as
        examples, fold them into a surviving section only if they
        genuinely belong there.
     c. Do not auto-pick a replacement project for the category —
        note any still-Current sibling/successor project you're aware
        of (e.g. one already sitting in "New candidates") but leave
        promoting it into the tracked table to a human.
   - Otherwise (still current, or Planned Completion Date not yet
     passed), pull 2-4 current example tasks assigned to AI-Dev-US
     team or Sam Mefford on that project (filter by assignee + status
     equatesWith NEW/INP, or by project ID if you need any-assignee
     examples for naming convention), and overwrite that project's
     section in the output file with the refreshed fields, example
     tasks, and a new `_Last refreshed: <ISO timestamp>_` line.
     Preserve the category-matching narrative text (confidence level,
     "why this project" reasoning) — only the field dump and
     example-task list are mechanically refreshed.

2. **Scan for new candidates.** Query `insights_find_workfront_data`
   for tasks assigned to Sam Mefford (or the AI-Dev-US team, if a team
   filter is available) with status `equatesWith` NEW/INP, grouped by
   project. For any project ID that appears here but is **not** in the
   tracked-projects table above:
   - First check it against **Excluded projects** — if it's on that
     list, skip it silently, no matter how many matching tasks it has.
   - Otherwise, run it through **Validity criteria** above. A project
     with matching tasks but a passed Planned Completion Date, a
     terminal status, a mismatched workspace, or no live epic/monthly-
     commit link is not a candidate — add it to **Excluded projects**
     with a one-line reason instead of "New candidates", so it's never
     re-surfaced or re-checked.
   - Only projects that pass all four validity criteria go under
     `## New candidates (needs review)`: project name + URL, 1-2
     example tasks, and the date first seen. Do not guess which of the
     tracked categories it belongs to — that's a human call.
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
  to re-derive project IDs from scratch. (Checking a single candidate
  project against the current view for criterion 4 is fine and
  expected; re-deriving the whole view from scratch is not.)
- Auto-assigning a newly discovered project to one of the tracked
  categories instead of appending it to "New candidates (needs review)".
- Treating "has a task with a matching bracket tag" as sufficient
  evidence for a candidate — always run it through **Validity
  criteria** first. A stray task on a completed, cancelled, past-due,
  wrong-workspace, or commit-less project is not a real candidate.
- Re-suggesting a project that's already in **Excluded projects** just
  because it still has matching tasks — exclusions are durable until a
  human removes them, not re-evaluated every run.
- Appending to a project's section instead of overwriting it, leaving
  stale duplicate field dumps behind.
- Hand-building Workfront URLs instead of using the `url` field on
  returned objects.
