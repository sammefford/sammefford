---
name: pyramid-summarize
description: Summarize a folder of mixed-format documents (PDF, PPTX, DOCX, VTT, HTML, MD, TXT, repos) into a two-tier pyramid summary hierarchy. Produces one per-doc summary per source, a master index (master.md), and a navigation guide (pyramid_summaries.md). Use when asked to summarize a folder of documents, create a knowledge base from a set of files, or build a searchable summary hierarchy.
user-invocable: true
---

# Pyramid Summarize

Turns a folder of mixed-format source files into a navigable two-tier summary hierarchy:

```
summaries/
  per-doc/           ← one .md per source
  master.md          ← index: abstract + metadata for every source
pyramid_summaries.md ← navigation guide for future consumers
```

## Arguments

The user provides:
- `<source-folder>` — the directory containing the files to summarize. If not provided, ask before proceeding.
- `--output <output-folder>` *(optional)* — where to write the `summaries/` tree and `pyramid_summaries.md`. Defaults to `<source-folder>` (output lives alongside the sources). Use a different path when the source folder is read-only or you want to keep sources and summaries separate.

**All output paths in Steps 0–6 use `<output-folder>`, not `<source-folder>`, as the root.**

---

## Step 0 — Prerequisites

First, check whether poppler is already installed. If not, invoke the `change-logging` skill before installing it:

```bash
which pdftotext 2>/dev/null && echo "poppler already installed" || echo "needs install"
```

If poppler is missing:
1. Invoke `/change-logging` to log the install
2. Then run: `brew install poppler`

Then create the output directory:

```bash
mkdir -p "<output-folder>/summaries/per-doc"
```

**No temporary files are created.** All extraction commands pipe directly to Claude (PPTX via `unzip -p`, PDF via `pdftotext`, DOCX via `textutil`, VTT/HTML/MD via shell pipes). Nothing lands on disk except the final `.md` files written in Steps 3–6. Large VTT files are chunked in memory using `sed -n` line ranges — no intermediate files.

---

## Step 1 — Inventory

List all files in the source folder (non-recursive unless instructed) and group by format:

| Group | Extensions / patterns |
|-------|----------------------|
| Plain text | `.md`, `.txt`, `.csv` |
| HTML | `.html`, `.htm` |
| DOCX | `.docx`, `.doc` |
| PDF | `.pdf` |
| PPTX | `.pptx` (check size; see large-file note below) |
| VTT | `.vtt` |
| Repos | any `~/dev/<name>` paths listed by the user |

```bash
ls -lh "<source-folder>"
```

Note file sizes. Files over 50M are likely video-embedded PPTXs — treat them as large-file PPTXs (slide XML only).

---

## Step 2 — Per-format extraction commands

Run the appropriate command for each source file to get text to summarize.

### PPTX (all sizes)
```bash
unzip -p "FILENAME.pptx" 'ppt/slides/slide*.xml' 'ppt/notesSlides/notesSlide*.xml' 2>/dev/null \
  | sed 's/<[^>]*>/ /g' | tr -s ' \n' ' '
```
For very large PPTXs (>50M, typically contain embedded video): this command is still fast because it extracts XML only and skips `ppt/media/`. Note in the summary that video/image content was not captured.

### PDF
```bash
pdftotext "FILENAME.pdf" -
```

### DOCX
```bash
textutil -convert txt -stdout "FILENAME.docx"
```

### VTT (transcript captions)
```bash
grep -vE '^(WEBVTT|[0-9]+$|[0-9]{2}:[0-9]{2}|^[[:space:]]*$)' "FILENAME.vtt" \
  | sed 's/<[^>]*>//g' | grep -v '^$'
```
VTT files over 200K: chunk into thirds using `sed -n '1,<N>p'`, summarize each third, then combine into one summary file.

### HTML
```bash
textutil -convert txt -stdout "FILENAME.html"
```

### MD / TXT
Read directly with the Read tool.

### Git repos (from local clones)
```bash
cat ~/dev/REPONAME/README.md
cat ~/dev/REPONAME/CLAUDE.md 2>/dev/null
cat ~/dev/REPONAME/AGENTS.md 2>/dev/null
find ~/dev/REPONAME -maxdepth 2 -type f -name "*.md" | head -30
```

---

## Step 3 — Per-doc summary template

Write each summary to `<output-folder>/summaries/per-doc/<slug>.md` using this template:

```markdown
# [Document Title]
**Presenter/Author:** ...
**Format:** PPTX | PDF | VTT | DOCX | repo | web | MD
**Source file:** filename as it appears in the source folder (or repo path)
**Topic:** one sentence describing what this is about

## Abstract
2–3 sentences: what this is about and what it concludes.

## Key Points
- bullet 1
- bullet 2 ...

## Conclusions / Decisions / Recommendations
What was decided, recommended, or called out as important.

## Open Questions / Outstanding Items
Anything flagged as unresolved.

## Key People & Projects
Names, team names, project codenames mentioned.

## Notes
Image-heavy slides, missing content, video placeholders, or other extraction limits.
```

**Slugs**: derive from the filename — lowercase, hyphens for spaces, no extension.
Example: `AI_Factory_Summit_Fixy.pptx` → `fixy-agent201.md`

---

## Step 4 — Process all sources

Work through each source file using a TodoWrite list. Mark each item done immediately after writing its summary file. Batch extraction commands in parallel where the files are independent.

**Extraction strategy by volume:**
- Up to 5 files: extract all in parallel, then write summaries in parallel
- 6–20 files: group by format, extract group in parallel, write in parallel
- 20+ files: work in batches of 5, complete each batch before moving to the next

---

## Step 5 — Generate `summaries/master.md`

After all per-doc summaries exist, read them and generate `<output-folder>/summaries/master.md`:

```markdown
# [Corpus Title] — Master Summary
Generated: <date>

## What this is
One paragraph: purpose of this document set, date range, number of sources, main themes.

## Document index
| File | Author/Presenter | Format | Topic | Abstract |
|------|-----------------|--------|-------|---------|
| [slug.md](per-doc/slug.md) | Name | format | Topic | 2-sentence abstract |
...one row per source...

## Cross-cutting themes
Bullet list of themes that appeared across multiple sources.

## Key entities referenced
Table: name, description, related doc(s). Include projects, people, tools, or concepts that appear in multiple sources.

## Action items & open questions
Consolidated list across all docs.
```

---

## Step 6 — Write `pyramid_summaries.md`

Write the navigation guide at `<output-folder>/pyramid_summaries.md` (same level as `summaries/`):

Cover these five topics:

1. **The two-tier model**: `master.md` (abstracts + index) → `per-doc/*.md` (full summaries) → original source files (deepest tier, only when a summary is insufficient).

2. **Navigation recipe**: start by reading only `master.md`; use the document index table and cross-cutting themes to pick 1–5 relevant `per-doc/` files; read those; drop to the original file (path in each summary's `Source file:` field) only if the summary lacks needed detail.

3. **Token budget guidance**: `master.md` alone is cheap to load every session; the full `per-doc/` set fits in one context window; never bulk-load original files.

4. **What's missing**: list any content NOT summarized (video, images, web-only pages, password-protected files) so consumers know when to go to a human or the source.

5. **How to extend**: to add a new doc, follow `PLAN.md`'s template + extraction commands (or re-invoke `/pyramid-summarize`), write a new `per-doc/<slug>.md`, then add a row to `master.md`'s index table.

---

## Quality checklist before reporting done

- [ ] Every source file has a corresponding `<output-folder>/summaries/per-doc/*.md` summary
- [ ] No summary file has placeholder text (`...`, `TODO`, `[TBD]`)
- [ ] `<output-folder>/summaries/master.md` has one row per source in the Document Index table
- [ ] `<output-folder>/pyramid_summaries.md` exists
- [ ] Large-file PPTXs note "video content not captured" in their Notes section
- [ ] VTT files note "video not captured; text transcript only"
- [ ] No temporary files were created (extraction commands all piped; nothing to clean up)

---

## Output file map (for confirmation)

```
<output-folder>/
  pyramid_summaries.md       ← navigation guide
  summaries/
    master.md                ← index of all sources
    per-doc/
      <slug-1>.md
      <slug-2>.md
      ...
```

The source files in `<source-folder>` are **never modified**.

---

## Reporting to the user

When complete, output:
- Total per-doc files written and their location (`<output-folder>/summaries/per-doc/`)
- Location of `master.md` and `pyramid_summaries.md`
- Any sources that failed extraction (format, error, workaround attempted)
- Any sources skipped (web-only links, password-protected files, etc.)
- Confirmation that no temporary files were created and no cleanup is needed
