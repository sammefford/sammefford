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

4. If the config belongs in the user's dotfiles repo and `/Users/sammefford/projects/sammefford/mac` exists, mirror the edited file there after making changes. Preserve the home-relative path under `mac/`. Locally created skills (any new `SKILL.md` under `~/.claude/skills/` or `~/.cursor/skills/`, including their supporting files) always get mirrored, even if that skill has no prior mirror in `mac/` yet — don't skip mirroring just because it isn't already tracked there:

```text
~/.zshrc                                              -> /Users/sammefford/projects/sammefford/mac/.zshrc
~/.claude/hooks.json                                  -> /Users/sammefford/projects/sammefford/mac/.claude/hooks.json
~/.claude/skills/change-logging/SKILL.md              -> /Users/sammefford/projects/sammefford/mac/.claude/skills/change-logging/SKILL.md
~/.cursor/skills/change-logging/SKILL.md              -> /Users/sammefford/projects/sammefford/mac/.cursor/skills/change-logging/SKILL.md
~/.local/bin/tool-name                                -> /Users/sammefford/projects/sammefford/mac/.local/bin/tool-name
```

5. After an important persistent change, record a short note:

```bash
~/.cursor/skills/change-logging/scripts/log-change.sh config ~/.zshrc "Added ~/.local/bin to PATH"
```

Use the modified file or persistent resource as the target, not an API name, domain, or logical label. For macOS defaults changes, target the backing plist:

```bash
defaults write com.todesktop.230313mzl4w4u92 ApplePressAndHoldEnabled -bool false
~/.cursor/skills/change-logging/scripts/log-change.sh config ~/Library/Preferences/com.todesktop.230313mzl4w4u92.plist "Disabled Cursor press-and-hold alternate character popup"
```

6. After mirroring any config file to `/Users/sammefford/projects/sammefford/mac`, always commit and push the change — no additional authorization needed. Before committing, run `git status` in the mac repo, review the relevant diff, and stage only the intended `mac/` paths. Use a concise commit message describing what changed and why. Never commit files containing secrets, tokens, credentials, private keys, or unrelated local changes.

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
