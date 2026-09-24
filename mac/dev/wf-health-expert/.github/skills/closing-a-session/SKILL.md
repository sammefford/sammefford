---
name: closing-a-session
description: Close a wf-health-expert coding session when asked to /closing-a-session, close out, or finish. Use this workspace policy instead of the personal closing-a-session fallback; verify Poetry checks and preserve concurrent work.
---

# Closing a wf-health-expert Session

This workspace skill takes precedence over the personal `closing-a-session` fallback. Do not import another repository's push-to-main, GitLab MR, or cleanup policy.

1. Inspect `git status --short`, the current branch, relevant diffs, and `git worktree list`. Identify only this session's changes. Leave other sessions' untracked files, edits, and running processes alone; never stage everything or discard work to obtain a clean tree.
2. Verify changed code with the narrowest relevant checks. For Python changes, use the configured Poetry environment and focused `poetry run pytest tests/unit/...` checks; use `poetry run flake8 --count wf_health_expert` when lint is relevant. `bin/unit_test.sh` and `bin/lint.sh` both run `poetry install`, so do not invoke them just to close a session when no install is needed. Run integration or end-to-end checks only when their services and credentials are available and the change warrants them. Report anything not run.
3. Record actionable follow-ups in the project's existing tracker if one is available, avoiding duplicates. Do not turn unrelated failures into unrequested refactors. If a finding cannot be recorded, call it out explicitly.
4. Do not commit, push, rebase, merge, open a GitLab MR, or remove a worktree unless asked or required by an applicable repository instruction. Before any requested commit, use `commit-with-workfront-task`, stage only this session's files, and follow this repository's current branch and review policy. Never push directly to `main` by assumption; never remove a worktree with unmerged work.
5. Report verification results, changes published (if any), unrelated work left untouched, and remaining blockers or follow-ups.