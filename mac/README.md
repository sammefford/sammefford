# mac dotfiles

Personal macOS config for Sam Mefford. Files mirror their home-directory paths under this repo root.

## What's tracked

| Repo path | Live path | Purpose |
|-----------|-----------|---------|
| `.zshrc` / `.zprofile` / `.profile` | `~/` | Shell config |
| `.config/karabiner/karabiner.json` | `~/.config/karabiner/` | Karabiner-Elements keyboard remapping |
| `.claude/settings.json` | `~/.claude/` | Claude Code global permissions, model, env vars |
| `.claude/hooks.json` | `~/.claude/` | Claude Code lifecycle hooks (session-start, stop, notification → cmux) |
| `.claude/skills/change-logging/` | `~/.claude/skills/change-logging/` | Global skill: log config changes (SKILL.md only; scripts live in `.cursor/`) |
| `.cursor/skills/change-logging/` | `~/.cursor/skills/change-logging/` | Same skill with shell scripts (snapshot, log, mirror, run-and-log) |
| `.claude/skills/{inbox,workfront,backlog,triage}/` | `~/.claude/skills/` | Work-triage skill set: `/triage` orchestrator + `/inbox`, `/workfront`, `/backlog` sub-skills (source only — `.claude/skills/.gitignore` excludes `reports/` and `*-user-id.txt`, which hold real colleague/Workfront data and personal IDs and must never be published) |
| `.local/bin/claude-cmux-hook` | `~/.local/bin/` | Claude Code → cmux notification bridge |
| `Library/Application Support/Cursor/User/keybindings.json` | `~/Library/Application Support/Cursor/User/` | Cursor keybindings |
| `backlog.md` | `~/backlog.md` (symlink → repo) | Flat work-capture list, triaged via the `/backlog` skill. Unlike the copied dotfiles above, `~/backlog.md` is a **symlink** to this repo file so frequent appends are auto-tracked. |

## New machine setup

Clone the repo, then copy files to their live locations:

```bash
git clone git@github.com:sammefford/sammefford.git ~/projects/sammefford/mac
cd ~/projects/sammefford/mac

# Shell
cp .zshrc .zprofile .profile ~/

# Karabiner
mkdir -p ~/.config/karabiner
cp .config/karabiner/karabiner.json ~/.config/karabiner/

# Claude Code
mkdir -p ~/.claude/skills/change-logging
cp .claude/settings.json .claude/hooks.json ~/.claude/
cp .claude/skills/change-logging/SKILL.md ~/.claude/skills/change-logging/

# change-logging scripts (used by both Claude and Cursor)
mkdir -p ~/.cursor/skills/change-logging/scripts
cp .cursor/skills/change-logging/SKILL.md ~/.cursor/skills/change-logging/
cp .cursor/skills/change-logging/scripts/* ~/.cursor/skills/change-logging/scripts/
chmod +x ~/.cursor/skills/change-logging/scripts/*.sh

# cmux hook
mkdir -p ~/.local/bin
cp .local/bin/claude-cmux-hook ~/.local/bin/
chmod +x ~/.local/bin/claude-cmux-hook

# Cursor keybindings
mkdir -p ~/Library/Application\ Support/Cursor/User
cp Library/Application\ Support/Cursor/User/keybindings.json \
   ~/Library/Application\ Support/Cursor/User/
```

## Skills

Skills are prompt instructions + optional shell scripts that Claude Code or Cursor invoke via `/skill-name`. Global skills (installed to `~/.claude/skills/` or `~/.cursor/skills/`) are available in every project.

### change-logging

Tracks installs, config edits, and persistent machine changes so they're auditable and reversible.

**Invoke before:** editing dotfiles, karabiner config, shell config, Claude/Cursor settings, or installing tools.

**What it does:**
1. Snapshots the target file to `~/.local/state/config-snapshots/`
2. Logs a note to `~/.local/state/agent-change-log/CHANGELOG.md`
3. Mirrors the edited file to this dotfiles repo
4. Commits and pushes the change

**Scripts** (in `~/.cursor/skills/change-logging/scripts/`):

| Script | Purpose |
|--------|---------|
| `snapshot-config.sh <file> <reason>` | Snapshot a config file before editing |
| `log-change.sh config <file> <note>` | Record a change note |
| `mirror-to-dotfiles.sh <file>` | Copy a file to its repo mirror path |
| `run-and-log.sh install <reason> -- <cmd>` | Run a command and log its output |

## How changes flow back

When Claude Code edits a tracked file, it uses `change-logging` to snapshot → edit → mirror → commit → push. The mac repo is always up to date after any agent-assisted config change.

## Project-level skills

Workspace-specific skills (catalyze-verify, create-pr, deploy-release, etc.) live in the project repo at `~/dev/catalyze-specs/.claude/skills/` and are versioned there — they don't belong here.
