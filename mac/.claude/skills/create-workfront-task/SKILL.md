---
name: create-workfront-task
description: "Create one or more tasks in the Adobe internal Workfront \"hub\" instance (hub.workfront.com), following the logging conventions actually used by Erika O'Neal and the team (bracket-tag naming, hour estimates, plain statuses, project routing) rather than generic defaults. Use this whenever the user asks to log, create, add, or file a Workfront task or to-do — for themselves or to assign to someone else — including phrases like \"log a task in Workfront/hub for X\", \"create a task for <person>\", \"add this to my Workfront tasks\", \"file a SOC-2/launch/security task\", or \"make one of these per client\" (batch/templated tasks). Also use when the user wants their Workfront tasks to look like a teammate's or match a project's existing task style. Do NOT use for generic Workfront project/portfolio/issue creation unrelated to tasks — that's the manage-workfront-workflow skill's job."
metadata:
  author: user
---

# Create Workfront Task (hub conventions)

Generic Workfront task creation just needs a name and a project. But on hub.workfront.com, tasks that follow the team's actual conventions are easy to spot against ones that don't — no bracket tag, no hour estimate, an exotic status picked from the org-wide list. This skill fills in those conventions so a task you create reads like one Erika O'Neal or the team would have logged, not a generic placeholder.

This skill is a thin, opinionated layer on top of the workfront-hub MCP server's stable tools (`insights_find_id_by_name`, `insights_search_users`, `workflow_read_workflow_docs`, `workflow_create_any_object`). It doesn't reinvent those — it tells you which conventions to apply before calling them.

## Before creating: gather 5 things

Work through these in order. Ask the user only for what you can't infer from context — don't interrogate them on things a reasonable default answers.

1. **Assignee** — self (the current user) unless the user names someone else.
2. **Project** — a named shared project/initiative, or "no particular project" (→ personal tasks project).
3. **Category tag(s)** — see the tagging convention below.
4. **Scope** — a single task, or a batch of near-identical tasks (one per client/target/etc).
5. **Description** — see the description convention below. Don't skip this even for a short task name; the name is a label, the description is what makes the task actionable later.

## 1. Resolve the assignee

Default to the current session user — call `insights_get_current_user` if you don't already know who that is this session.

If the user names someone else ("create a task for Erika", "assign this to the design team lead"):
- Resolve their user ID with `insights_find_id_by_name` (entity `user`) or `insights_search_users` if the name is ambiguous.
- Do this resolution and the task creation in the **same turn** — the MCP server's chaining rule applies here same as any other write: never stop after just the lookup.

## 2. Resolve the project

Two cases:

- **Shared initiative named or implied** ("log this under the LLM Gateway Migration project", "add it to the security tracker"): resolve the project name to an ID with `insights_find_id_by_name` (entity `project`).
- **No shared project, personal one-off**: every user has an auto-created personal project literally named `"<Full Name>'s Tasks"` (e.g. `Sam Mefford's Tasks`, `Erika O'Neal's Tasks`). Resolve *the assignee's* personal project this way, not the requester's — if you're creating a task for someone else with no named project, it goes on **their** tasks project, not yours.

If you're unsure which case applies, ask — don't guess a project name.

## 3. Apply the tag-prefix naming convention

Real tasks on hub aren't named with plain descriptions alone — they're prefixed with one or more `[TAG]` blocks that categorize the work, then the plain description. Observed examples:

```
[SOC-2] [Service Workfront AI Agent Service] Penetration Testing
[LA] Runbooks creation
[LA] Security assessments - Josh confirmed this is Threat Modeling
```

Tags seen in practice and what they mean:

| Tag | Meaning |
|---|---|
| `[SOC-2]` | Compliance/audit workstream item |
| `[Service: <name>]` or `[Service <name>]` | Names which service/system the work is for |
| `[LA]` | Launch Activity — an action item feeding a launch checklist |
| `[AI]` | AI-initiative area (also seen on project names, e.g. `[AI] Security Operations 2026-H2`) |

These aren't an exhaustive enum — teams coin their own tags for their own tracked workstreams. If the task clearly belongs to one of the above, use it. If it's for a different named initiative or compliance program, ask the user what tag they'd use, or look at sibling tasks in the same project (`insights_find_workfront_data` on `task.task_name` filtered by project) and match the pattern already in use there.

**Skip the tag entirely** only for genuine personal one-offs with no tracked category — a task on someone's personal "`<Name>'s Tasks`" project doesn't need one just to have one. Don't force a tag where the source data didn't have one.

## 4. Estimate hours — don't leave it at 0

Set `workRequired` deliberately rather than defaulting to zero:

- **Granular action items** (a single checklist-style step): default to **4 hours** unless the user gives you a different number.
- **Rollup/workstream tasks** (something that represents a chunk of work with its own sub-items): use a round number matching its actual scope — 20, 32, 36, 180 are all real examples from workstream-level tasks. Ask the user for a ballpark if it's not obvious from the task description.
- Only leave it at 0 if the user explicitly says this is a placeholder or tracking-only item with no real effort behind it.

## 5. Write a detailed description — always

The task `name` is a bracket-tagged label, not a spec. Never leave `description` empty and never let it just restate the name. Write it so someone with zero conversation context — a teammate, or an AI agent asked to "implement this task" — could pick it up and act without asking a clarifying question first.

A description that meets that bar covers, in prose or short sections as fits the task:

- **What / why** — the concrete problem or gap being addressed, and why it matters (the motivation, not just the symptom).
- **Where** — specific file paths, functions, config keys, project/case names, URLs — whatever anchors the work to real artifacts. Pull these from the conversation; don't invent generic placeholders.
- **Current vs. desired behavior** — what happens today, and what should happen instead, concretely enough to tell when it's done.
- **Suggested approach** — if the conversation already surfaced one (a pattern to copy, a file that already does this correctly), name it. Don't invent a design that wasn't discussed.
- **Acceptance check** — how to know the task is done (a command to run, a case to re-test, a specific observable outcome).

Draw every one of these from the actual conversation and codebase investigation that led to the task, not from generic boilerplate about the task name. If you don't have enough detail on one of these points, say so in the description rather than inventing filler — but don't skip the section header, since a future reader (or AI) needs to know that point wasn't settled yet.

Skip a full write-up only for genuine one-line personal reminders with no implementation content (e.g. "renew badge photo") — anything with a "how" behind it gets a real description.

## 6. Use plain statuses only

hub's status field has 60+ custom values across different objects and projects (things like `Awaiting Code/QA Review`, `CAB-Certified`, `Design in Progress`) — these belong to specific project templates, not general use. Unless you've confirmed the target project's template expects one of those, stick to the plain default set:

**New, In Progress, Complete, Cancelled**

New tasks should almost always start as **New** unless the user says otherwise.

Call `workflow_read_workflow_docs` before setting any status value you haven't already confirmed for this project — status codes aren't guessable, and the wrong one can send a task into someone else's approval workflow.

## 7. Batches / templated tasks

When the ask is "one of these per X" (per client, per environment, per team, per SB sandbox, etc.), don't invent N different names — reuse one base stem and append a short distinguishing suffix per instance, matching the real pattern:

```
AI Dev US - Configure & Validate New SB03 - CL01 & Merck
AI Dev US - Configure & Validate New SB03 - CL05
AI Dev US - Configure & Validate New SB03 - CL09
```

Confirm the base stem and the list of suffixes with the user before firing off a batch of creates — it's cheap to double check, expensive to clean up ten wrongly-named tasks.

## Creating the task

Once the above is resolved, create with `workflow_create_any_object`:

```json
{
  "objectType": "task",
  "fields": {
    "name": "[LA] Runbooks creation",
    "description": "What/why, where (files/paths/URLs), current vs. desired behavior, suggested approach, and an acceptance check — per the description convention above. Plain text or lightweight markdown, not a restatement of the name.",
    "projectID": "<resolved project ID>",
    "assignedToID": "<resolved user ID>",
    "workRequired": 4,
    "status": "NEW",
    "plannedCompletionDate": "2026-09-17T00:00:00Z"
  }
}
```

`plannedCompletionDate` is optional — only include it if the user gave a due date or the surrounding project has an obvious one (e.g. matching sibling tasks' due dates in the same project). `description` is not optional — see step 5.

After creating, confirm back to the user in plain language: the task name (with its tag), who it's assigned to, which project it landed in, the hour estimate, and a one-line recap of what the description covers — so they can catch a wrong guess before it sits in someone's list.

## Update the local brief

Every task created here (whether assigned to the current user or to someone else) belongs in the local brief at `/Users/sammefford/projects/hub/claude_automated/workfront-tasks-brief.md` — that file is what `commit-with-workfront-task` checks and what `/sync-tasks` otherwise regenerates from a fresh API pull. Update it in the same turn as creation so the task shows up there immediately, without waiting for the next `/sync-tasks` run:

1. Read the current file.
2. For each task just created, build a bullet in the exact format `sync-tasks` uses: `- <task name link> — <project name link> — due <date or "no due date">`, using the `url` the create call returned for the task and the project (don't hand-build URLs). Format the due date as `M/D/YY` if one was set, matching the existing rows.
3. Insert each new bullet into the list at the position that keeps it sorted by due date ascending, with no-due-date rows staying at the end — don't just append to the bottom.
4. Leave the `_Last synced: <ISO timestamp>_` line untouched — this is an incremental insert, not a full resync, so don't claim a sync time that didn't happen.
5. If the file said `No open tasks.` because it was empty, replace that line with the new bullet list.

This only keeps the brief in sync for tasks created through this skill — it's not a substitute for `/sync-tasks`, which is still the source of truth for completions, reassignments, and status changes made outside this flow.

## Common mistakes

- Creating a plain-named task ("Runbooks creation") when the surrounding project's other tasks are all tagged — check sibling tasks before assuming no tag is needed.
- Leaving `description` empty, or filling it with a restatement of the name ("Create the thing described in the title") — that gives an AI or teammate nothing to act on.
- Writing a description from generic boilerplate instead of the specific files/paths/URLs/behavior actually discussed in the conversation.
- Leaving `workRequired` at 0 by default instead of asking or applying the 4-hour default for granular items.
- Picking an exotic status from the global list because it "sounded closer" — plain New/In Progress/Complete/Cancelled is correct unless you've verified the project's template requires otherwise.
- Routing a task for someone else onto *your* personal tasks project instead of theirs.
- Firing off a batch of tasks with inconsistent or guessed suffixes instead of confirming the stem + suffix list with the user first.
- Skipping `workflow_read_workflow_docs` before setting a non-default status.
