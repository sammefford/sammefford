---
name: tools-qa-run-sync
description: Use when the user wants to download, pull, or sync run/result/test-case data from the mcp-eval-app tools-qa instance for local inspection or report dev. Writes a browsable JSON tree to ~/mcp-eval-app-tools-qa-sync/mcp-eval-runs/.
---

# Tools-QA Run Sync

## Overview

Mirrors one or more runs (+ their results + every test case those results
reference) from the live `mcp-eval-app` tools-qa instance into a local,
browsable directory tree — one JSON file per run/result/test-case — so past
runs can be inspected or diffed locally without touching the live instance
again. Wraps `~/dev/mcp-eval-app/api/scripts/sync_run_bundle.py`, which is
the same HTTP client the app's own History page "Export selected" button
uses under the hood.

This is read-only against the tools-qa instance — it never writes back to it.

## Output location

`~/mcp-eval-app-tools-qa-sync/mcp-eval-runs/<out-subdir>/`

- `meta.json` — base_url, run_ids, fetched_at
- `runs/<runId>.json`
- `results/<runId>.json`
- `test_cases/<testCaseId>.json` — deduped across all fetched runs
- `datadog/` — left empty (no Datadog export endpoint yet)

Pick `<out-subdir>` to match what the user asked for: a single run id when
they name one run, or a short descriptive label (e.g. a date or a batch
name) when syncing several runs together. Don't overwrite an existing
`<out-subdir>` with a different set of runs without checking with the user —
directories under `mcp-eval-runs/` are treated as durable snapshots, not a
scratch cache.

## Auth

`sync_run_bundle.py` needs `MCP_EVAL_SESSION` (a tools-qa session cookie).
The user keeps a valid one in `~/dev/mcp-eval-app/api/.env` and refreshes it
there when it expires — **never** `cat`/`grep`/print that file (global
secrets rule; the value must never appear in chat or tool output).

Use the bundled wrapper, which sources `.env` internally and never echoes
it:

```
.claude/skills/tools-qa-run-sync/scripts/sync.sh <out-subdir> <run-id> [run-id ...]
```

(run from the repo root — this skill is local to `mcp-eval-app`, not `~/.claude/skills`)

If this fails with 401s, tell the user `MCP_EVAL_SESSION` in
`api/.env` has probably expired and needs a fresh cookie from Chrome
DevTools (see `sync_run_bundle.py`'s docstring) — don't try to work around
it yourself.

## Steps

1. Get the run id(s) to sync from the user (or from a prior step in the
   conversation, e.g. a run just kicked off or looked up via the API).
2. Pick an `<out-subdir>` per the naming guidance above.
3. Run `scripts/sync.sh <out-subdir> <run-id> [run-id ...]`.
4. Report what was written (run/result/test-case counts, from the script's
   own summary line) and the output path — don't re-print the JSON contents
   unless the user asks to see something specific from it.

## Common mistakes

- Trying to `source`/read `api/.env` directly instead of using the wrapper
  script — that's exactly the pattern the global secrets rule and the
  sandbox both block.
- Using `uv`/`glab` bare — they're not on this shell's PATH; the wrapper
  already calls `/opt/homebrew/bin/uv` directly.
- Using `export_run_dataset.py` (single portable JSON bundle, meant for
  re-import into another backend) when the user wants a browsable per-run
  tree — that's `sync_run_bundle.py`'s job, and it's what this skill wraps.
