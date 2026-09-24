---
name: closing-a-session
description: Close out a coding session when the user says /closing-a-session, close out, or finish this session. Verify this session's work, preserve unrelated changes, and report outstanding follow-ups.
---

# Closing a Session

Before following this fallback, check the current workspace for `.github/skills/closing-a-session/SKILL.md`, `.agents/skills/closing-a-session/SKILL.md`, or `.claude/skills/closing-a-session/SKILL.md`. If one exists, load and follow that workspace skill instead; do not apply the steps below. This makes the workspace policy authoritative even if the personal skill was selected first.

1. Identify what this session actually changed. Inspect `git status`, the relevant diff, and `git worktree list` where applicable. Treat other sessions' edits and untracked files as someone else's; never stage, revert, stash, or delete them as part of cleanup.
2. Run focused checks for this session's changes. Report any failures and distinguish them from pre-existing issues. Do not claim a passing verification you did not run.
3. Check for unfinished work or actionable findings. Record follow-ups in the project's existing tracker when appropriate, without creating duplicates. Do not silently expand the original task.
4. Commit, push, merge, or remove a worktree only if requested or required by the current project's instructions. Follow the repository's branch and review policy; never assume direct-to-main or mandatory PR/MR. Stage only this session's files and do not discard unmerged work.
5. Summarize what was verified, what was published, and what remains. If a step was blocked, say why and leave the work in a recoverable state.