# Workfront Status Codes
**Presenter/Author:** Workfront (`mcp__workfront-hub__workflow_read_workflow_docs`, `workfront://reference/status-codes`)
**Format:** MD
**Source file:** status-priority-fields.md
**Topic:** Enum values for project/task/issue statuses, project condition codes, priority, issue severity, and issue types on hub.workfront.com.

## Abstract
Reference table of every status/enum code the Workfront API uses for projects, tasks, and issues (OpTasks), plus priority levels, condition codes, issue severity, and issue types. This is the lookup table for interpreting or filtering on any status/priority field returned by `insights_find_workfront_data` or `planning_search_records`.

## Key Points
- Project statuses: `CUR` (Current), `PLN` (Planning), `CPL` (Complete), `DED` (Dead), `ONH` (On Hold), `REQ` (Requested), `APR` (Approved), `REJ` (Rejected), `IDA` (Idea).
- Task statuses: `NEW`, `INP` (In Progress), `CPL` (Complete, percentComplete = 100).
- Issue (OpTask) statuses: `NEW`, `INP`, `AWA` (Awaiting), `ONH`, `CPL`, `CLS` (Closed), `WNR` (Won't Resolve).
- Priority values are numeric 0–4: `0` None, `1` Low, `2` Normal, `3` High, `4` Urgent.
- Issue severity is numeric 1–5, separate from priority: `1` Cosmetic through `5` Fatal error.
- Issue types (`opTaskType`): `BUG`, `RQS` (Request), `ISS` (Issue), `CRQ` (Change Request).
- Project condition codes (`OT`/`AR`/`IT`) are distinct from status — they signal schedule health, not lifecycle stage.

## Conclusions / Decisions / Recommendations
For the workfront skill: "not yet complete" for tasks means status `_Mod: notin` `["CPL"]`; for issues it means excluding `CPL`, `CLS`, and `WNR`. Priority tier ranking (Urgent > High > Normal > Low) maps directly to descending numeric priority `4 > 3 > 2 > 1`.

## Open Questions / Outstanding Items
None — this is a static reference table, not a decision doc.

## Key People & Projects
None (reference table only).

## Notes
No extraction limits; doc is a clean markdown table already.
