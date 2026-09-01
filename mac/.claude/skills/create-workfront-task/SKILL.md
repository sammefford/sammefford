---
name: create-workfront-task
description: "Create one or more tasks in the Adobe internal Workfront \"hub\" instance (hub.workfront.com), following the logging conventions actually used by Erika O'Neal and the team (bracket-tag naming, hour estimates, plain statuses, project routing) rather than generic defaults. Use this whenever the user asks to log, create, add, or file a Workfront task or to-do — for themselves or to assign to someone else — including phrases like \"log a task in Workfront/hub for X\", \"create a task for <person>\", \"add this to my Workfront tasks\", \"file a SOC-2/launch/security task\", or \"make one of these per client\" (batch/templated tasks). Also use when the user wants their Workfront tasks to look like a teammate's or match a project's existing task style. Do NOT use for generic Workfront project/portfolio/issue creation unrelated to tasks — that's the manage-workfront-workflow skill's job."
metadata:
  author: user
---

# Create Workfront Task (hub conventions)

Real hub tasks have a bracket tag, an hour estimate, and a plain status — not generic defaults. Thin layer over workfront-hub's stable tools (`insights_find_id_by_name`, `insights_search_users`, `workflow_read_workflow_docs`, `workflow_create_any_object`).

## Gather before creating

1. **Assignee** — self unless named.
2. **Project** — named initiative, or personal tasks project.
3. **Tag(s)** — see convention below.
4. **Scope** — single task or batch.
5. **Description** — always required, even for short task names.

Only ask the user for what you can't infer.

## 1. Assignee

Default: current session user (`insights_get_current_user` if unknown).

Named other person: resolve ID via `insights_find_id_by_name` (entity `user`) or `insights_search_users` if ambiguous, then create in the **same turn** — never stop after the lookup.

## 2. Project

- **Named shared initiative**: resolve via `insights_find_id_by_name` (entity `project`).
- **Invoked from a repo with a mapped project** (see Repo-aware routing below): use that
  project — it beats the personal-project fallback.
- **No named project and no repo mapping**: use the *assignee's* auto-created personal
  project, `"<Full Name>'s Tasks"` — not the requester's.

Ask rather than guess if unclear.

### Repo-aware routing

When the working directory is inside one of these repos, default to its mapped project and
tag instead of the personal-tasks fallback — the goal is that where a task gets filed follows
where the work actually is, not stale habit from a repo you've since moved off of:

| Repo (cwd) | Project | Tag |
|---|---|---|
| `mcp-eval-app` | Run Eval Tests (`https://experience.adobe.com/#/@adobeinternalworkfront/so:hub-Hub/workfront/project/6a66359b0000042c21ac0f735a9237b8`) | `[mcp-eval-app]` |
| `renzler-service` | Renzler-Service (`https://experience.adobe.com/#/@6AD033CF62197E1C0A495FDD@AdobeOrg/so:hub-Hub/workfront/project/6a8caaa80000700fdf61f747b995d4e4`) | `[renzler-service]` |

Not in the table: fall back to the normal Project/Tag rules in this skill — ask if unclear
rather than guessing a new mapping. If you're working in a repo that used to route to a
different tag (e.g. old `[renzler]`/`[renzler-service]`-tagged tasks from before work moved to
`mcp-eval-app`), don't carry that old tag forward — use the current repo's mapped tag.

### Jessie He / Matt Newman routing

Both work outside renzler now — never reference renzler (paths, case names, harness internals) in their tasks. Route both to project **`[Enterprise Context] Business Context MCP — Workfront Planning`** (`https://experience.adobe.com/#/@6AD033CF62197E1C0A495FDD@AdobeOrg/so:hub-Hub/workfront/project/6a2c62980002b3fdf3d9ed2ebb3e931d`) — where the bulk of each of their current enterprise-context tasks already live.

- **Jessie He** — tenant-fixture / enterprise-context-instance-data tasks. Link description to the real object(s) via the `url` the enterprise-context MCP tools return — never hand-build, never substitute a renzler path.
- **Matt Newman** — prompt wording / case granularity / setup-teardown tasks. Link to matching test case(s) in the `mcp-eval-app` GitLab project, where he now works.

## 3. Tag-prefix naming

Tasks are named `[TAG] ... plain description`, e.g.:

```
[SOC-2] [Service Workfront AI Agent Service] Penetration Testing
[LA] Runbooks creation
```

| Tag | Meaning |
|---|---|
| `[SOC-2]` | Compliance/audit |
| `[Service: <name>]` | Names the service/system |
| `[LA]` | Launch Activity |
| `[AI]` | AI-initiative area |

Not exhaustive — for other initiatives, ask the user or match sibling tasks in the same project (`insights_find_workfront_data` on `task.task_name` filtered by project).

Skip the tag only for genuine personal one-offs on a "`<Name>'s Tasks`" project.

## 4. Hours

- **Granular item**: 4 hours default.
- **Rollup/workstream**: round number matching scope (20/32/36/180 are real examples) — ask if unclear.
- **0** only if explicitly a placeholder/tracking-only item.

## 5. Description — always required

Never empty, never a restatement of the name. Must let someone with zero context act without a clarifying question. Cover:

- **What/why** — the gap and its motivation.
- **Where** — real file paths, config keys, project/case names, URLs from the conversation — no placeholders.
- **Current vs. desired** — concrete enough to know when it's done.
- **Suggested approach** — only if already discussed; don't invent one.
- **Acceptance check** — how to verify done.

If a point wasn't settled in conversation, say so rather than inventing filler — but keep the header.

Whole-document references (handoff/plan/spec file): don't paste the local disk path — it's meaningless off-machine. Attach via an in-session upload tool (e.g. `approvals__upload_document_ui`) and note it's attached; if no upload tool is available, say so and ask the user to attach it.

Skip full write-up only for one-line personal reminders with no "how" (e.g. "renew badge photo").

## 6. Status

Use only **New, In Progress, Complete, Cancelled** — hub has 60+ project-template-specific values (e.g. `CAB-Certified`) that don't apply generically. Default new tasks to **New**.

Call `workflow_read_workflow_docs` before any non-default status — wrong status can misroute into an approval workflow.

## 7. Batches

Reuse one base stem + short suffix per instance, matching real patterns:

```
AI Dev US - Configure & Validate New SB03 - CL01 & Merck
AI Dev US - Configure & Validate New SB03 - CL05
```

Confirm stem + suffix list with the user before firing off a batch.

## Creating the task

```json
{
  "objectType": "task",
  "fields": {
    "name": "[LA] Runbooks creation",
    "description": "What/why, where, current vs. desired, suggested approach, acceptance check.",
    "projectID": "<resolved project ID>",
    "assignedToID": "<resolved user ID>",
    "workRequired": 4,
    "status": "NEW"
  }
}
```

`plannedCompletionDate` — omit by default. Set only on an explicit user date or an unambiguous project pattern; don't infer from unrelated sibling due dates. If a date is unavoidable with nothing real to base it on, use exactly one year out.

Confirm back: task name+tag, assignee, project, hours, one-line description recap.

## Update the local brief

Update `/Users/sammefford/projects/hub/claude_automated/workfront-tasks-brief.md` in the same turn — it's what `commit-with-workfront-task` checks and `/sync-tasks` regenerates.

1. Read the file.
2. Add bullet: `- <task link> — <project link> — due <date or "no due date">` (use returned `url`s; date as `M/D/YY`).
3. Insert sorted by due date ascending, no-due-date rows last — don't append blindly.
4. Leave `_Last synced: <timestamp>_` untouched.
5. Replace `No open tasks.` if that was the prior state.

Not a substitute for `/sync-tasks` (source of truth for completions/reassignments/status changes made elsewhere).

## Common mistakes

- Defaulting to the personal-tasks project/an old tag from habit when the cwd matches a repo
  in the Repo-aware routing table — check that table before falling back to personal.
- Plain-named task in an all-tagged project — check siblings first.
- Empty or name-restating `description`.
- Generic-boilerplate description instead of conversation specifics.
- `workRequired` left at 0 by default.
- Exotic status picked because it "sounded closer."
- Someone else's task routed to *your* personal project.
- Batch suffixes guessed instead of confirmed.
- Skipping `workflow_read_workflow_docs` before a non-default status.
- Local disk path pasted in place of an attached document.
- Renzler referenced in a Jessie He / Matt Newman task.
- `plannedCompletionDate` set out of habit rather than left unset.
