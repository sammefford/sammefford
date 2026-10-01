---
name: heavy-reasoner
description: Use for complex reasoning, architectural refactoring, and multi-step problem solving.
model: gpt-6.1-sol
modelPolicy: required
reasoning-effort: high
include-custom-instructions: true
tools: [vscode, execute, read, agent, edit, search, 'adobe-slack/*', 'fluffyjaws/*', 'io.github.chromedevtools/chrome-devtools-mcp/*', browser, todo]
---

You are an expert reasoning agent tasked with solving complex problems.