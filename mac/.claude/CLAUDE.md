# Global Claude Instructions

## Secrets & Credentials

**Never expose secret values in chat output or tool call arguments.**

- Never read the contents of `.env`, `.npmrc`, `*.pem`, `*.key`, credential files, or any file that likely contains secrets
- Never run commands which might return secrets nor pass secret values as arguments to Bash commands where they might appear in the chat log (e.g., `echo "$SECRET"`, `ps -ef | grep command_known_to_accept_secret_as_an_arg`, `base64 -d "$SECRET_VALUE"`)
- When working with secrets, reference only the **environment variable name** — never the value
- Never decode, print, or log JWT tokens, API keys, client secrets, passwords, or access tokens
- If a task requires inspecting a secret value (e.g., decoding a JWT to check its claims), run the decode in a script that writes output to a temp file and read only the non-sensitive fields — or ask the user to paste only the non-sensitive decoded fields

## Be Cost Efficient

Use subagents as appropriate.  Use subagents with cheaper models or less effort
where you can to reduce costs, and more powerful subagents or more effort when
real intelligence is best.  Don't use the main agent / model for everything.

## Concurrent / Parallel Sessions

Assume a real (non-worktree) working dir may have another session (user or agent) editing it concurrently, any time.

- Working-tree changed since you last looked, and you didn't cause it — don't `restore`/`checkout --`/`clean`/overwrite it without asking; could be a parallel session's work.
- Don't give subagents write access to the real checkout unless the task needs it and the user asked. Prefer isolated worktrees; if a subagent needs the real path, scope it to read-only (`log`/`diff`/`show`/`Read`) explicitly in the prompt. Worktree isolation doesn't block absolute-path writes (`git -C <realpath> ...`) — handing over a real path = granting write access there.
- Commit/push only what this session discussed — don't sweep up unrelated uncommitted edits.
- `git stash` to isolate concurrent edits needs confirmed pause of other sessions first — and must be popped before finishing, so paused sessions resume where they left off.

## Session Prompts

When asked for a "prompt" for another session, deliver it as copy/paste-ready markdown inside a fenced code block.

## Screenshot Evaluation

Prefer Haiku for interpreting screenshots, instead of evaluating images inline in the main session.

- When a screenshot needs interpreting (e.g. `mcp__chrome-devtools__take_screenshot`, verifying a rendered UI), save it to a file (`filePath`), then dispatch an `Agent` call with `model: "haiku"` to read the image and report back a description or verdict against the specific check you need.
- Keep the main session's job to deciding what to check and acting on the verdict.

@RTK.md
