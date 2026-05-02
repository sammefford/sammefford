---
name: change-logging
description: Logs installs, package changes, persistent system changes, and config edits. Use before installing or updating tools/dependencies, changing shell/editor/Claude/Cursor/cmux config, editing dotfiles, or making important local machine changes that should be auditable and reversible.
---

# Change Logging

## Required Workflow

Use this skill before any install, package update/removal, persistent machine change, or config-file edit.

1. Preserve permission clarity. If a command needs user approval, prefer running the real command directly so the approval prompt clearly shows the operation, for example `brew install ripgrep` or `npm install package-name`.

2. For installs or commands whose full output matters, use the logging wrapper only when it does not obscure the permission being granted:

```bash
~/.cursor/skills/change-logging/scripts/run-and-log.sh install "Short reason" -- command arg1 arg2
```

If wrapping would make the approval less clear, run the real command directly and record a short note afterward.

3. Before editing a small config file, snapshot the current file:

```bash
~/.cursor/skills/change-logging/scripts/snapshot-config.sh ~/.zshrc "Short reason"
```

4. If the config belongs in the user's dotfiles repo and `/Users/sammefford/projects/sammefford` exists, mirror the current file there before editing so Git can show the change. Preserve the home-relative path when practical:

```text
~/.zshrc                 -> /Users/sammefford/projects/sammefford/.zshrc
~/.claude/hooks.json     -> /Users/sammefford/projects/sammefford/.claude/hooks.json
~/.local/bin/tool-name   -> /Users/sammefford/projects/sammefford/.local/bin/tool-name
```

5. After an important persistent change, record a short note:

```bash
~/.cursor/skills/change-logging/scripts/log-change.sh config ~/.zshrc "Added ~/.local/bin to PATH"
```

## Log Locations

- Command output: `~/.local/state/agent-change-log/YYYY-MM-DD/`
- Change notes: `~/.local/state/agent-change-log/CHANGELOG.md`
- Config snapshots: `~/.local/state/config-snapshots/`

## Rules

- Never log secrets, tokens, credentials, private keys, or full secret-bearing environment dumps.
- Do not wrap commands that require interactive password entry if the transcript could capture sensitive input.
- Do not wrap commands when wrapping makes Cursor/Claude permission prompts less specific than the underlying operation.
- Keep summaries short and specific enough to explain why the change happened.
- If logging fails, tell the user before making the persistent change.
