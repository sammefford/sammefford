---
name: backlog
description: Use when triaging ~/backlog.md, categorizing or deduping captured ideas/bugs/tasks, or deciding which backlog items are ready to become Workfront tasks. Drafts task promotions only — never creates them.
---

# Backlog Organizer

Triages the flat capture list at `~/backlog.md` — categorizes entries,
dedupes near-identical ones, and flags which are ready to act on.

## Capture format
`~/backlog.md` is a flat markdown list (`- <idea/bug/task text>`). Sam or
any session can append to it at any time with no structure required at
capture time. This skill imposes structure only at triage time.

## Procedure
1. Read `~/backlog.md`, noting the **exact line number** of each entry —
   this is the only real, live target a not-yet-promoted idea has, so it
   must survive into the report as a per-item link.
2. Categorize each entry as **idea**, **bug**, or **task**.
3. Dedupe near-identical entries (same underlying request worded
   differently) — note which lines were merged (keep the earliest line
   number as the link target for a merged entry).
4. For each entry, flag it **ready** (concrete, scoped, actionable as
   written) or **raw** (still needs thinking-through before it's actionable).
5. For every **ready** entry, draft a proposed Workfront task/issue (title
   + description). **Do not create it** — creating a Workfront object is a
   confirmed action back in the invoking session, per Sam's standing
   instruction to confirm actions visible to others or hard to reverse.
   Never call any Workfront create/update/delete tool from this skill.
6. Write the full report to
   `~/.claude/skills/backlog/reports/YYYY-MM-DD.md` (today's
   date; **overwrite** if it already exists), with a `## Categorized`
   section (all entries, category + dedupe notes) and a `## Ready to
   promote` section listing each proposed title/description pair awaiting
   approval. **Every entry in both sections must link to its source
   line** in `~/backlog.md`, using a plain absolute path with a
   line-number fragment (this renderer does not resolve heading-slug
   anchors like `#ready` — only `path#L<line>` links actually jump), e.g.
   `[source](/Users/sammefford/backlog.md#L9)`. Do not add a heading
   anchor to the `## Ready to promote` heading itself — it doesn't
   resolve in this renderer, and nothing should be linking into this
   report file anyway (see `/triage`, which links only to real external
   sources or this same `backlog.md#L<line>` target, never into this
   report).
7. Reply in chat with a short summary: counts by category, how many are
   ready to promote, and the report file path.

## Error handling
If `~/backlog.md` doesn't exist or is empty, say so plainly and stop — do
not fabricate entries.
