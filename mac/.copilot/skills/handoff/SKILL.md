---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up.
argument-hint: "What will the next session be used for?"
---

Write a markdown handoff document summarising the relevant portions of the current conversation so a fresh agent can continue the work. Save to the temporary directory of the user's OS - not the current workspace.

Include a "suggested skills" section in the document, which suggests skills that the agent should invoke.

Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

Add instructions to use subagents for specialized tasks to get the best balance of quality vs token cost.  Use large models and more reasoning for planning and strategy.  Use smaller models and less reasoning for running things or routine tasks.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.

Do not conduct research in preparation for the next session.  The handoff document should be based on the current conversation only, and should delegate the relevant research to the next session.

After saving the doc, delegate opening and submitting a new GitHub Copilot Chat Editor to a subagent using `runSubagent` with `model: "Claude Sonnet 5.5 (copilot)"`. This model requirement applies to the launcher subagent, NOT the new chat. Leave the new chat's model unchanged unless the user separately requests a specific model. If the launcher model is unavailable, report the blocker rather than silently substituting another model.

Give the launcher subagent the workspace path, saved handoff path, and a short prompt summarizing the task and instructing it to read the doc, e.g. `Continue auth refactor; read handoff doc: <path>`. Scope it to launching the chat only: no research, configuration changes, or edits to the handoff or workspace files. Require it to:

1. Activate VS Code and verify the intended workspace window is in front.
2. Use macOS System Events to press `Cmd+Shift+P`, type `Chat: New Chat Editor`, and press Return. Verify the new `Chat — <workspace>` editor is in front before entering anything.
3. Type the short prompt into the verified chat input and press Return to send it. Never press Return in an unverified window or in the Command Palette after typing the prompt.
4. Verify submission through the visible submitted request or the new session transcript's exact `user.message`. An empty editor or unsent draft is not success. Return verification evidence and any blocker to the parent agent.

If macOS accessibility access is denied, explain the blocker instead of claiming the handoff was launched. `code chat --reuse-window --maximize "<prompt>"` can submit a Copilot chat without accessibility access, but it does not guarantee a Chat Editor tab; use that only when a sidebar chat is acceptable