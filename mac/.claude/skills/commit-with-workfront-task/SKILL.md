---
name: commit-with-workfront-task
description: Use before running any `git commit` other than /change-logging commits — checks that a Workfront task exists for the work being committed, using the local brief at ~/projects/hub/claude_automated/workfront-tasks-brief.md, before letting the commit proceed.
---

# Commit With Workfront Task

## Overview

Every commit except for local machine config changes should trace back to a
logged Workfront task. Before running `git commit`, check the local task brief
for a task that matches the work being committed. If none exists, stop and use
`create-workfront-task` (`/create-workfront-task`) to log one first — then
commit.

## Brief file

`/Users/sammefford/projects/hub/claude_automated/workfront-tasks-brief.md`

This is a snapshot, not live data — it's refreshed by the `sync-tasks` skill
and can be stale. Treat a miss here as "no task found in the last sync," not
definitive proof no task exists.

## Steps

1. Read the brief file.
2. Look for a task whose name or project plausibly matches the change being
   committed (repo name, feature, bug, service tag like `[Service X]`,
   ticket-style keywords in the commit message). Matching is a judgment
   call, not an exact string match — a task titled "[Service renzler-service]
   Fix broken mcp eval cases" covers a commit fixing eval test data in that
   service, for example.
3. **If a plausible task is found:** proceed with the commit normally. No
   need to mention the task unless the user would find it useful context.
4. **If no plausible task is found:** stop before committing. Tell the user
   no matching Workfront task was found in the brief, and offer to run
   `/create-workfront-task` to log one first. Only proceed with the commit
   without a task if the user explicitly says to skip logging one.
5. If the brief file itself looks stale (e.g. last sync is old, or the user
   says a task was just created), re-run `sync-tasks` to refresh it before
   deciding there's no match.

## Common mistakes

- Treating a brief miss as certain — it's a snapshot; re-sync if it might be stale.
- Blocking the commit silently instead of asking the user — always surface the missing-task finding and let them decide.
- Doing exact string matching on task names instead of judging relevance to the actual change.
- Forgetting this check entirely on `git commit -m ...` invocations that don't go through a longer conversation.
