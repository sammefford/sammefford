# Workfront Prioritization Algorithm (v1)

Kept separate from SKILL.md so this can be tweaked without touching the
skill's orchestration prompt.

## Ranking order
1. **Overdue** tasks/issues first (past their due date, not yet complete).
2. Then by **priority tier**: Urgent > High > Normal > Low.
3. Within a tier, **soonest due date first**.

**Numeric priority mapping (authoritative):** `4`=Urgent, `3`=High,
`2`=Normal, `1`=Low, `0`=None — higher number = higher priority. This
matches `references/raw-docs/status-priority-fields.md`. Ignore the live
`task_priority` field-hint text that claims "1 is highest priority" — it
contradicts the enum's own `possibleValues` and is wrong. Rank by the
mapping above.

## Recommended next action per item (pick exactly one)
- **Push forward** — top priority / due soon: do it next.
- **Follow up** — blocked or waiting on someone else: name who to ping
  (use the assignee/owner field on any blocking predecessor task, or the
  most recent comment author if there's an open question).
- **Defer** — low priority relative to everything else in the list:
  explicitly OK to leave for now.

Each item's recommendation needs a one-line reason tied to the ranking
criteria above (e.g. "Overdue by 3 days" or "Normal priority, due in 3
weeks — lower items need attention first").

## Tuning this file
This algorithm is v1. If Sam asks for a different ranking (e.g. weight by
project instead of pure priority tier), edit this file only — do not move
the logic into SKILL.md.
