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
3. Link every bullet straight to its **real external source** — never to
   a spot in another skill's report file, and never to a markdown heading
   anchor (`#slack`, `#ready`, `#task-x`, etc.), which this renderer
   doesn't resolve anyway. No cross-linking between report files, full
   stop — each bullet's link comes from the underlying system:
   - **Workfront** item → that task's `url` field.
   - **Slack** item → that message's `permalink`.
   - **Email** item → that message's `webLink`.
   - **Backlog** item → the `~/backlog.md#L<line>` source link the
     `backlog` report already carries for that entry (backlog ideas have
     no Workfront/Slack/Outlook home until promoted, so their capture
     line in `~/backlog.md` is the real source — reuse the link the
     backlog report already computed, don't re-derive it).
   ```
   - 3 emails waiting → [details](https://outlook.office365.com/owa/?ItemID=...)
   - WF task X overdue → [details](https://experience.adobe.com/#/@.../workfront/task/<id>)
   - 2 backlog items ready → [details](/Users/sammefford/backlog.md#L9)
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
