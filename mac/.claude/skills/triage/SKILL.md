---
name: triage
description: Use when Sam wants a single compact triage signal across email/Slack, Workfront priorities, and backlog — a quick "what needs my attention right now" rollup. Do not use for detailed reports on any one source; use /inbox, /workfront, or /backlog directly for that.
---

# Work Triage

Thin orchestrator. Calls `inbox`, `workfront`, and `backlog` and compresses
their results into an ultra-compact rollup. **Adds no data-gathering logic
of its own.**

## Procedure
1. Invoke all three sub-skills in parallel — via the `Skill` tool (or
   parallel subagents), not sequentially:
   - `inbox` (produces `~/.claude/skills/inbox/reports/<today>.md`)
   - `workfront` (produces `~/.claude/skills/workfront/reports/<today>.md`)
   - `backlog` (produces `~/.claude/skills/backlog/reports/<today>.md`)
2. From each sub-skill's own report, pick the single most important signal
   (e.g. "3 emails waiting", "task X overdue", "2 backlog items ready").
3. Render **at most 5 bullets, at most 5 words each** (not counting the
   link), each bullet linking to the relevant report file with an anchor,
   using a plain absolute filesystem path — not a `file://` URI:
   ```
   - 3 emails waiting → [details](/Users/sammefford/.claude/skills/inbox/reports/2026-08-06.md#emails)
   - WF task X overdue → [details](/Users/sammefford/.claude/skills/workfront/reports/2026-08-06.md#task-x)
   - 2 backlog items ready → [details](/Users/sammefford/.claude/skills/backlog/reports/2026-08-06.md#ready)
   ```
4. This 5-bullet/5-word cap applies **only** to this rollup. Never
   summarize a sub-skill's report further than one bullet, and never
   expand past 5 bullets even if all three sources have multiple flagged
   items — pick the single most important thing per source.

## Error handling
If a sub-skill fails (e.g. Workfront auth expired), still render bullets
for the other two. Replace the failed one with a one-line error bullet
(e.g. "Workfront: auth expired, run /workfront directly"). Never drop a
source silently or retry it invisibly.
