---
name: log-defect
description: "Log a defect (bug/request) against a Workfront product on the hub.workfront.com instance, routed through the '*Workfront Product Issues' queue with the correct Defect Severity and Application Area custom fields. Use whenever the user asks to log, file, report, or create a defect or bug in Workfront/hub — including phrases like 'log a defect for X', 'file a bug in hub', 'report this issue against <product>', or 'create a defect for the MCP move action problem'. Do NOT use for plain Workfront tasks (that's create-workfront-task) or for generic project/portfolio/issue creation unrelated to a product defect."
metadata:
  author: user
---

# Log Defect (hub.workfront.com)

A defect logged through this skill should look like one filed through the real
`*Workfront Product Issues` request queue — landing in the right destination project,
carrying a real `DE:Defect Severity` and `DE:Application Area` value, not left blank or
guessed generically. This is a thin, opinionated layer on top of the `workfront-hub` MCP
server's stable tools (`insights_find_id_by_name`, `insights_search_fields`,
`workflow_read_workflow_docs`, `workflow_create_any_object`) — it tells you which values to
use, not how the tools work.

## Before creating: gather 3 things

1. **What happened** — repro steps, expected vs. actual, impact. Write this in the user's
   own words plus whatever detail they gave; don't pad it with invented detail.
2. **Application Area** — see resolution steps below.
3. **Defect Severity** — see resolution steps below. Don't over-inflate.

## 1. Title and description

- Title: `[Bug] <short description>` — mirrors the real convention (e.g. `[Bug] workfront-hub
  MCP update_any_object 'move' action returns not available for this account`).
- Description: plain prose covering Repro / Expected / Actual / Impact, in that order, when
  the user's report has those parts. Don't force the structure if the user only gave a short
  one-line complaint — a short description is fine.
- The title means the built-in `name` field, not a custom `DE:Name` field.
  Likewise, a requested issue status means the built-in `status`, not `DE:Status`.
  Discover these fields with `insights_search_fields` before writing. If MCP reports
  a collision, follow its explicit-confirmation requirement: ask once which field
  the user intends, then retry with `fieldDisambiguation` using that answer. Reuse
  an explicit confirmation already given for this create; do not repeatedly ask.
  Never send `fieldDisambiguation` speculatively before a reported collision.
- Keep the description within the tool's 4000-character limit. Include verified
  evidence links and distinguish confirmed facts from root-cause hypotheses.

## 2. Resolve Application Area

Pick **one** value from the `DE:Application Area` picklist — a large enumeration (150+
values) grouped by product/team prefix (`WF:`, `Proof:`, `Workfront Fusion:`, `AI:`, `SRE:`,
`ESM`, `WF Integration:`, `WF Planning:`, etc).

Read
`/Users/sammefford/projects/hub/teams_and_areas_of_ownership/application_areas.md` for the
full reference — one line per value with a short description, grouped by prefix, plus a
"Notes on ambiguity" section at the bottom for tie-breaking. Don't inline all the values
here; that file is the source of truth and may be updated independently of this skill.

Tie-breaking rules from that file (repeated here since they're easy to forget):
- Prefer the most specific area (e.g. `WF: Timesheets` over `WF: Time Tracking` for a
  timesheet-approval bug).
- If a bug spans UI + backend (e.g. a list is slow because of a DB issue), pick the
  user-visible symptom's area, not the infra cause.
- Use `Security Issue (Area TBD)` only when the report is security-sensitive AND the
  functional area is genuinely unclear.

If nothing in the reference file fits, ask the user rather than picking the closest-sounding
generic value — a wrong Application Area routes the defect to the wrong team.

## 3. Resolve Defect Severity — don't over-inflate

`DE:Defect Severity` is a 4-value enum. Submit the numeric code (as a string), not the label:

| Code | Label | Use when... |
|---|---|---|
| `2` | Critical | Major outage, data loss, or no workaround exists for a blocking problem. |
| `3` | High | Breaks key functionality; a workaround may exist but it's painful. |
| `4` | Medium | Bug with a workaround; annoying but doesn't block work. |
| `5` | Low | Minor/cosmetic issue, edge case, or something with an easy workaround. |

Default bias: **don't over-inflate.** Most one-off bugs reported casually ("this field looks
wrong", "this action fails in an edge case") are Low or Medium, not High or Critical. Reserve
Critical/High for things that are actually blocking someone's work right now or losing data.
If genuinely unsure between two adjacent levels, ask the user rather than picking the higher
one by default.

## 4. Target the `*Workfront Product Issues` queue

Use an authenticated **hub.workfront.com MCP connection**, not Chrome DevTools
when MCP is available. Verify the target from returned object URLs; a generic
Workfront tool prefix does not identify its tenant. Do not file in devtest as a
substitute, or treat an expired browser tab as evidence that MCP is unavailable.

**Submission queue and destination project are different objects.** Submit to
the project named `*Workfront Product Issues`. Its `Workfront` topic routes the
created issue into `Internal Issues`. Do not send `Internal Issues` as the create's
`projectID`: MCP rejects it as a non-enabled request queue (observed 2026-09-30).

1. Resolve the submission project with
  `insights_find_id_by_name(entity="project", name="*Workfront Product Issues")`.
  Use that returned ID as `data.projectID`, and complete the create in the same turn.
2. Resolve `Internal Issues` separately only when needed to inspect recent routed
  defects or verify the final destination. Its ID is not the submission ID.
3. Confirm the queue definition and `Workfront` topic IDs from a recent real
  submission using `insights_find_workfront_data`, with fields
  `issue.issue_queueDefID` and `issue.issue_queueTopicID`. These are standard API
  fields `queueDefID` and `queueTopicID`, not `DE:` custom fields. The verified
  values on 2026-09-30 were `4e4aeebe000436f1c59ac81d1ec42d65` and
  `4e4af55a00043c27d7939e52e54d6d29`, respectively. Re-verify rather than relying
  on these indefinitely; do not attach an unrelated topic.
4. Follow the MCP queue-form requirements. Read the queue's visible request
  fields and required custom fields when the available tools expose them. Use
  the user's supplied or approved values; ask for missing required values, not
  values already approved in the defect draft. Do not invent priority or dates.

Call `insights_read_docs("mcp-usage")` before Insights queries, and load the
condition/sort guides those queries require. Call `workflow_read_workflow_docs`
with `workfront://tools/create-any-object` before this non-trivial create.
For an explicit status, also read the status-code guide before sending it.

## Creating the defect

```json
{
  "objectType": "issue",
  "data": {
    "name": "[Bug] <short description>",
    "projectID": "<resolved '*Workfront Product Issues' project ID>",
    "description": "<repro / expected / actual / impact>",
    "queueDefID": "<verified queue definition ID>",
    "queueTopicID": "<verified Workfront topic ID>",
    "DE:Application Area": "AI: MCP",
    "DE:Defect Severity": "<resolved severity code>"
  }
}
```

(`objectType: "issue"` maps to the API's `optask` under the hood — the tool description
handles this; don't pass `optask` directly.)

The example leaves status and assignment to Workfront's defaults. If the user
requests New/unassigned, verify those outcomes rather than assuming routing
preserves them. When a status write is needed, use the discovered standard field
and the user's confirmed disambiguation if MCP requires it.

After creating, read back the issue by its returned ID and verify the title,
standard status, assignment, routed project, queue/topic IDs, Application Area,
and Defect Severity. A multi-select Application Area may be stored as
`["AI: MCP"]`; if readback confirms the sole selected value is `AI: MCP`, that
representation warning does not require another write. Do not blindly retry a
successful create because it returned a warning; that creates duplicates.

Confirm back to the user: the title, Application Area, Defect Severity (and why),
verified status/assignment, and the returned issue URL. Use the URL verbatim.
Update any local investigation report from draft/blocked to filed and include
the issue link. Sign the report posted on the user's behalf per their preferences.

## Common mistakes

- Picking a generic/closest-sounding Application Area instead of checking the reference
  file's exact picklist strings — values must match verbatim (they're a strict enum).
- Over-inflating severity because the user sounds frustrated — severity reflects actual
  impact (blocking/data-loss vs. cosmetic/workaround-exists), not tone.
- Writing `DE:Application Areas` (plural — a different, non-writable rollup field) instead of
  `DE:Application Area` (singular — the real writable enum field).
- Hardcoding `queueDefID`/`queueTopicID` forever without ever re-verifying — they're stable
  but admin-configurable; re-check via a recent real issue if creation fails or behaves
  unexpectedly.
- Skipping `workflow_read_workflow_docs` before the create call.
- Confusing the routed `Internal Issues` destination with the enabled submission
  queue, or using browser login state to judge MCP access.
- Writing to custom `DE:Name` or `DE:Status` when the user means the built-in title
  or status, or ignoring the MCP tool's explicit field-confirmation requirement.
