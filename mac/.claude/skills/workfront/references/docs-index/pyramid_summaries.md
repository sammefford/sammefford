# How to Navigate This Docs Index

This folder is a two-tier pyramid summary of the Workfront reference docs the
`workfront` skill depends on (status/priority enums, `_Mod`/`_Range` date
filters, and `orderBy` sorting), cached from
`mcp__workfront-hub__workflow_read_workflow_docs` so the skill doesn't have to
re-fetch them on every run.

## 1. The two-tier model
- **Tier 1 — `summaries/master.md`**: one-paragraph purpose statement, a
  document index table (file, topic, 2-sentence abstract), cross-cutting
  themes, key entities, and open questions across all three cached docs.
- **Tier 2 — `summaries/per-doc/*.md`**: one full summary per source doc
  (`status-priority-fields.md`, `date-filters.md`, `order-by.md`), each with
  Abstract / Key Points / Conclusions / Open Questions / Notes sections.
- **Deepest tier — originals**: the raw fetched doc text lives in
  `../raw-docs/*.md` (one level up from this `docs-index` folder). Drop to
  these only if a per-doc summary is missing a specific syntax detail (e.g.
  the exact case-insensitive modifier list).

## 2. Navigation recipe
1. Start with `summaries/master.md` for a fast overview and the document
   index.
2. Use the index to pick the 1 (rarely more than 1–2) relevant `per-doc/`
   file for the query-syntax question at hand.
3. Only if that summary lacks the needed detail, read the matching file in
   `../raw-docs/`.

For the `workfront` skill's actual runtime use, this file is a fallback —
the skill's normal path is `references/docs-index/pyramid_summaries.md` (this
file) or `summaries/master.md`, consulted only if a live Workfront query
about status/priority/date-filter/orderBy syntax needs clarification beyond
what's already baked into `references/prioritization.md`.

## 3. Token budget guidance
- `summaries/master.md` is small (under 1KB) — cheap to load every run if
  needed.
- The full `per-doc/` set (3 files, all short) fits comfortably in one
  context window; loading all three is fine if the master index doesn't
  answer the question.
- Never bulk-load `../raw-docs/*.md` — those are the full raw doc text and
  should only be read individually, on demand.

## 4. What's missing
- Nothing was skipped. All three raw docs were plain markdown text fetched
  directly from the `workflow_read_workflow_docs` tool — no PDFs, video,
  images, or password-protected content involved.
- Not covered by these three docs (out of scope for this cache): approval
  workflow docs, board/card docs, reporting/dashboard docs — none of those
  are needed by workfront's read-and-rank use case.

## 5. How to extend
To add a new cached doc (e.g. if workfront later needs a new Workfront
query-syntax topic):
1. Fetch it via `mcp__workfront-hub__workflow_read_workflow_docs` with the
   relevant `workfront://` URI.
2. Save the raw text to a new file under
   `~/.claude/skills/workfront/references/raw-docs/<topic>.md`.
3. Re-invoke the `pyramid-summarize` skill against that raw-docs folder
   (source-folder: `references/raw-docs`, output:
   `references/docs-index`), or manually add a `summaries/per-doc/<topic>.md`
   summary using the same template as the existing three, then add a row to
   `summaries/master.md`'s Document Index table.
