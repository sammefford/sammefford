# approve-allowlisted-chains

A Claude Code **PreToolUse** hook that auto-approves a chained Bash command when — and
only when — every command in the chain is already individually allowed by your
permission rules.

## Why this exists

Claude Code's built-in permission check already decomposes *simple* command chains and
auto-approves them when each piece matches an allow rule. But it bails to a manual
prompt on some chain shapes — empirically, mixing `&&` and `;` across many segments.
This command prompted even though every segment was individually allowlisted:

```
cd ~/dev/x && git rev-parse --abbrev-ref HEAD 2>&1; echo "---"; git rev-parse --short HEAD 2>&1; echo "---"; git log --oneline -1 2>&1
```

This hook closes that gap without loosening safety.

## What it does

On every Bash tool call it:

1. Parses the command with **bashlex** (a pure-Python port of bash's own grammar).
2. Refuses — stays silent, so a normal prompt happens — if the command is anything other
   than a plain chain of simple commands (see *Safety model*).
3. Splits the chain into segments and checks each against your `Bash(...)` allow/deny rules.
4. Emits `permissionDecision: "allow"` only if there are **≥2 segments**, **every** segment
   matches an allow rule, and **none** matches a deny rule.
5. Otherwise prints nothing and exits 0, so Claude Code prompts as usual.

It **never** emits `deny`.

## Safety model

The only dangerous divergence from Claude Code is *over*-approval — approving something CC
would not. The design makes that impossible instead of trying to replicate CC exactly:

- **Faithful parsing.** Splitting and danger-detection use bashlex, not string scanning, so
  we agree with the shell that actually runs the command. Refused outright: command/process
  substitution (`$(...)`, backticks, `<(...)`), compound commands (subshells, groups,
  `for`/`while`/`if`/`case`), function definitions, inline `VAR=val` assignments, heredocs,
  and any redirect other than an fd-dup (`2>&1`) or `/dev/null`.
- **Conservative allow matching.** `_allow_matches` is a deliberate *subset* of CC's rule
  semantics: exact match, or a single trailing wildcard (`verb *`, `verb:*`, `verb*`). Any
  mid-string or repeated `*` is treated as no-match. Under-matching only ever costs a
  prompt; it can never approve something CC would reject.
- **Liberal deny matching + backstop.** `_deny_matches` treats `*` as a full wildcard so it
  never *misses* a deny. And Claude Code re-applies its own deny rules *after* this hook
  regardless (a deny beats a hook's allow — verified), so a denied command is blocked even
  if this hook were wrong.
- **Fail-safe.** Any parse error, unknown construct, missing dependency, or unexpected input
  → print nothing, exit 0 → normal prompt.

Net: this hook can only ever make Claude Code prompt *more* than it would on its own, never
less.

## How it's wired

Registered in `~/.claude/settings.json` under `hooks.PreToolUse`, matcher `Bash`:

```json
{
  "matcher": "Bash",
  "hooks": [
    { "type": "command",
      "command": "/usr/bin/env python3 /Users/<you>/.claude/hooks/approve-allowlisted-chains/approve-allowlisted-chains.py",
      "timeout": 10 }
  ]
}
```

Several PreToolUse hooks can coexist; each decides independently. An `allow` from this hook
grants permission unless a deny rule (which CC always re-checks) blocks it.

## Dependency — one-time setup

The hook needs one package, **bashlex**. Install it once, with one command:

```
uv pip install --target ~/.claude/hooks/approve-allowlisted-chains/vendor bashlex
```

That's the whole setup. It drops bashlex into `vendor/` right next to the hook, which the
script adds to `sys.path` at startup — so it works under whatever `python3` Claude Code
runs the hook with, no venv to activate and no system `pip` to fight (on macOS this also
sidesteps Homebrew python's `externally-managed-environment` / PEP 668 refusal of a plain
`pip install`).

If bashlex is missing, the hook simply does nothing and you get normal
permission prompts, so a fresh clone degrades gracefully until you run it.

## Diagnostics

```
# Explain the verdict for a command against your REAL settings:
python3 approve-allowlisted-chains.py --check < cmd.txt

# cmd.txt holds the raw command (a file avoids shell-quoting headaches).
```

`--check` prints AUTO-APPROVE / DEFER plus a per-segment breakdown showing which rule
matched, or why the command was refused.

## Testing

- **Quick smoke test** (only needs the vendored bashlex):
  ```
  python3 approve-allowlisted-chains.py --selftest
  ```
- **Full unit suite:**
  ```
  python3 test_approve_allowlisted_chains.py     # standalone runner, no pytest needed
  pytest  test_approve_allowlisted_chains.py     # or under pytest
  ```

Both use fixed in-code rule fixtures (never your live settings) so results are
deterministic.

## Extending

The pieces are deliberately small and separable:

| Function | Responsibility |
|---|---|
| `_load_rules()`   | Read `Bash(...)` allow/deny patterns from the settings files CC reads. |
| `_bash_patterns()`| Pull inner patterns out of `Bash(...)` rule strings. |
| `_allow_matches()`| Conservative allow match. Extend *carefully* — looser matching risks over-approval. |
| `_deny_matches()` | Liberal deny match. Safe to widen; widening only adds prompts. |
| `_ChainInspector` | bashlex AST visitor: collects segments, flags unsafe constructs. |
| `_inspect()`      | Parse + walk → `(segments, reason)`. |
| `decide()`        | End-to-end `(command, allow, deny) -> bool`. |

When you change any of these, **add a case** to `test_approve_allowlisted_chains.py` (and,
for a quick built-in check, to `_selftest()` in the script). Golden rule for
`_allow_matches`: if you're unsure whether a change could match something CC wouldn't,
don't — bail instead.

## Known limitations (all fail *safe* — toward prompting)

- **Quoted `python3 -c "..."`-style rules don't match inside chains.** bashlex normalizes
  the outer quotes away, so the extracted segment (`python3 -c import yaml; ...`) can't match
  a quote-bearing rule. Standalone, CC still matches such rules directly. For inline use,
  prefer a wrapper script allowlisted by path.
- **Mid-string `*` allow rules are ignored** (e.g. `gh api repos/*/statuses *`). Conservative
  by design; such chains just prompt.
- **bash grammar, not zsh.** Exotic zsh-only syntax may not parse → bail → prompt.
- **`~/.claude/settings.local.json` is not read** (uncertain whether CC applies it to
  permissions; omitting it only makes the hook more conservative).

## Files

Everything is self-contained in `~/.claude/hooks/approve-allowlisted-chains/`:

```
approve-allowlisted-chains.py          the hook + --selftest + --check
README.md                              this file
test_approve_allowlisted_chains.py     unit suite
vendor/                                vendored bashlex
```
