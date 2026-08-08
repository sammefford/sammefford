---
name: closing-a-session
description: Use when a session is ending — the user says close out, finish this session, or similar — and there are uncommitted changes, an active worktree, or findings worth recording before stopping.
---

# Closing a Session

## Overview

This repo's session-close routine: verify → commit/push to `main` → clean up
the worktree → record findings. Unlike **superpowers:finishing-a-development-branch**
(which presents a merge/PR/keep menu), this repo integrates directly to
`main` with no PR step — that's this skill's deliberate, repo-specific
override.

**Announce at start:** "I'm using the closing-a-session skill to wrap up."

## Step 1: Scope What's Actually Yours

`git status` in this repo routinely shows other sessions' untracked/uncommitted
work (scratch scripts, draft docs, other worktrees' spillover) — this repo has
multiple concurrent Claude sessions as a norm, documented repeatedly in
`docs/future-enhancements.md`. Before staging:

- Stage only files this session actually created or edited. Never `git add -A`
  or `git add .` blind.
- If `git log`/`git status` shows commits or changes you didn't make since you
  last looked, don't `restore`/`checkout --`/`clean` over them — they're
  probably a parallel session's work, not a broken tree.

## Step 2: Finalize and Test

1. If there are changes to verify, run `yarn lint` and `yarn test` (unit). Fix
   or report failures — do not proceed to commit on a red suite.
2. If this session's changes touch code paths that talk to a real backend
   (Workfront MCP, Datadog, harness wrappers), verify against the real
   environment (`scripts/with-env.sh ...`) rather than a mocked dry run —
   this repo's convention is real-env proof, not a simulated pass.
3. If failures surface that you can't fix in-session, stop and report them
   instead of committing broken work.

## Step 3: Commit

- Before committing, check for a matching Workfront task the way
  **commit-with-workfront-task** describes (brief at
  `~/projects/hub/claude_automated/workfront-tasks-brief.md`) — offer to log
  one if nothing plausible matches, unless the user says to skip it.
- End the commit message with a `Co-Authored-By:` trailer naming whichever
  model is actually doing the work this session (e.g. `Co-Authored-By: Claude
  Sonnet 5`) — **never** append `<noreply@anthropic.com>` or any email.

## Step 4: Reconcile and Push to `main`

git fetch origin
git rebase --autostash origin/main   # not merge — keeps history clean

- If you're on a feature branch (e.g. in a worktree), fast-forward or merge
  it into `main` locally and push `main` — don't open a merge request. This
  repo's Claude sessions push straight to `main`; save MRs for when a human
  explicitly asks for one.
- If `git push` is rejected because the remote moved again, re-fetch and
  rebase — never force-push `main`.
- If a rebase or merge produces conflicts you can't resolve confidently,
  stop and ask rather than guessing.

## Step 5: Clean Up the Worktree

Only if this session was running in one (per `git worktree list`):

```bash
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"
git worktree remove .claude/worktrees/<name>
git branch -d worktree-<name>   # only after it's confirmed merged into main
git worktree prune
```

Skip this step entirely if you were never in a worktree, or if the branch
still has unpushed/unmerged work — leave it in place and say so instead of
force-deleting.

## Step 6: Update `docs/future-enhancements.md`

Skip this step if all work is completed and there are no findings worth recording.
If there are novel findings or clarifications needed, record them in this file.

1. Describe anything concrete a future session needs to pick this up (file
   paths, task IDs, repro steps) — match the existing entries' level of
   specificity, not a vague summary.
2. If something you read in this file turned out to be stale or wrong,
   delete it or reword it.

## Quick Reference

| Situation | Action |
|---|---|
| Tests failing | Fix the code or tests, — don't commit with failing tests |
| Untracked files not from this session | Leave them, don't stage or delete |
| Not in a worktree | Skip Step 5 entirely |
| Worktree branch not yet merged | Merge it to main before cleaning up the worktree |
| Push rejected | Rebase onto `origin/main`, retry — never force-push |
| Nothing changed this session | Skip straight to Step 6 only if there are findings worth recording |

## Common Mistakes

| Mistake | Reality |
|---|---|
| `git add -A` to "get everything committed" | Sweeps up other sessions' scratch/WIP files into your commit |
| Skipping tests because "it's just docs" | Still verify — commits to `main` land immediately, no PR gate catches it |
| `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` | Drop the email entirely — this repo's convention already moved past it |
| Force-pushing `main` after a rejected push | Rebase and retry instead; force-push only on explicit human request |
| Deleting a worktree with unpushed commits | Confirm the branch is fully merged into `main` first, or leave it |