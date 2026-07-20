# Global Claude Instructions

## Secrets & Credentials

**Never expose secret values in chat output or tool call arguments.**

- Never read the contents of `.env`, `*.pem`, `*.key`, credential files, or any file that likely contains secrets
- Never pass secret values as arguments to Bash commands where they would appear in the chat log (e.g., `echo "$SECRET"`, `base64 -d "$SECRET_VALUE"`)
- When working with secrets, reference only the **environment variable name** — never the value
- If a file must be read to understand structure (e.g., checking what keys exist), redact values before outputting: show key names only
- Never decode, print, or log JWT tokens, API keys, client secrets, passwords, or access tokens
- If a task requires inspecting a secret value (e.g., decoding a JWT to check its claims), run the decode in a script that writes output to a temp file and read only the non-sensitive fields — or ask the user to paste only the non-sensitive decoded fields
- `.env` files: treat as read-only for structure checks only; never output their contents

## Concurrent / Parallel Sessions

Assume a real (non-worktree) working dir may have another session (user or agent) editing it concurrently, any time.

- Working-tree changed since you last looked, and you didn't cause it — don't `restore`/`checkout --`/`clean`/overwrite it without asking; could be a parallel session's work.
- Don't give subagents write access to the real checkout unless the task needs it and the user asked. Prefer isolated worktrees; if a subagent needs the real path, scope it to read-only (`log`/`diff`/`show`/`Read`) explicitly in the prompt. Worktree isolation doesn't block absolute-path writes (`git -C <realpath> ...`) — handing over a real path = granting write access there.
- Commit/push only what this session discussed — don't sweep up unrelated uncommitted edits.
- `git stash` to isolate concurrent edits needs confirmed pause of other sessions first — and must be popped before finishing, so paused sessions resume where they left off.

## Screenshot Evaluation

Prefer Haiku for interpreting screenshots/visual state, instead of evaluating images inline in the main session.

- When a screenshot needs interpreting (e.g. `mcp__chrome-devtools__take_screenshot`, verifying a rendered UI), save it to a file (`filePath`) rather than inline, then dispatch an `Agent` call with `model: "haiku"` to read the image and report back a description or verdict against the specific check you need.
- Keep the main session's job to deciding what to check and acting on the verdict — not reading the pixels itself.
- Skip this for non-visual evidence (accessibility-tree snapshots, network logs, DOM text) — those are fine to read directly; this applies to actual image interpretation.