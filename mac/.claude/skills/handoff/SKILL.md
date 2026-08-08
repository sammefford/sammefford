---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up.
argument-hint: "What will the next session be used for?"
---

Write a markdown handoff document summarising the current conversation so a fresh agent can continue the work. Save to the temporary directory of the user's OS - not the current workspace.

Include a "suggested skills" section in the document, which suggests skills that the agent should invoke.

Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

Add instructions to use subagents for specialized tasks.  Use large models and more reasoning for planning and strategy.  Use smaller models and less reasoning for running things or routine tasks.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.

After saving the doc, open a new VS Code tab for the next session:

1. Compose a five-word (approx.) prompt summarizing the handoff task, ending with an instruction to read the doc, e.g. `Continue auth refactor — read handoff doc: <path>`.
2. URL-encode that prompt and run (macOS): `open "vscode://anthropic.claude-code/open?prompt=<encoded-prompt>"`.

This launches a fresh Claude Code session in a new tab pre-filled with the short prompt, which then reads the full handoff document.