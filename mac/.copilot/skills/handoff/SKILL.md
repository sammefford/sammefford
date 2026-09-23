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

After saving the doc, start a new GitHub Copilot chat in the current VS Code workspace:

1. Compose a five-word (approx.) prompt summarizing the handoff task, ending with an instruction to read the doc, e.g. `Continue auth refactor — read handoff doc: <path>`.
2. Run `code chat --reuse-window --maximize "<prompt>"` from the workspace directory. This sends the prompt immediately; it does not merely prefill the input. Do not use the Claude Code URI.
3. If the user wants the chat in an editor tab, use **Chat: Move Chat into Editor Area** in VS Code after the new chat opens. The CLI does not offer an editor-tab flag; do not claim it opened directly in an editor.

This starts a fresh Copilot session that reads the handoff document. If the `code` CLI is unavailable, tell the user to run **Chat: New Chat Editor** and paste the short prompt manually.