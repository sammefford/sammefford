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
   than a plain chain of simple commands, or a standalone compound command (see *Safety model*).
3. Splits the chain (or compound body) into segments. For each segment, canonicalizes just
   the leading command word if it's an absolute path into a known bin directory
   (`/usr/bin/tail` -> `tail`), and checks both the raw and canonicalized forms against
   your `Bash(...)` allow/deny rules.
4. Emits `permissionDecision: "allow"` only if **every** segment (including any nested
   inside a command/process substitution or compound body) matches an allow rule and **none**
   matches a deny rule, **and** either there are **≥2 top-level segments** (a chain), **or**
   there's exactly one top-level segment that is a compound command (for/if/while/subshell/
   group), **or** there's exactly one top-level segment whose canonicalization is what made
   it match (a single absolute-path command). A single ordinary command that already matches
   in its raw form is left to Claude Code's own native matching, unchanged from before.
5. Otherwise prints nothing and exits 0, so Claude Code prompts as usual.

It **never** emits `deny`.

## Safety model

The only dangerous divergence from Claude Code is *over*-approval — approving something CC
would not. The design makes that impossible instead of trying to replicate CC exactly:

- **Faithful parsing.** Splitting and danger-detection use bashlex, not string scanning, so
  we agree with the shell that actually runs the command. `for`/`if`/`while` and
  subshell/group compound commands are inspected rather than refused outright (see "Compound
  command support" section below); `case` statements, function definitions, and heredocs are
  refused outright anywhere. An inline `VAR=val` assignment is refused unless `val` is wholly
  a single command/process substitution (`VAR=$(cmd)`) — see "Variable assignment support"
  below for exactly what that lets through and the risk it knowingly reopens.
- **Real-file redirects are allowed only in a narrow, literal, resolvable case.** A
  redirect is approved if it's an fd-dup (`2>&1`), `/dev/null`, *or* an output redirect
  (`>`/`>>`) where the target is: (a) **literal text** — no `$VAR`, `$(...)`, or backticks,
  so the actual path can't depend on anything the hook can't see; (b) an **absolute path**
  — a relative path's real location depends on the effective cwd, which an earlier `cd` in
  the same chain could have changed, so it's always refused rather than guessed; (c) an
  extension in `_SAFE_REDIRECT_EXTENSIONS` (`.log`, `.out`, `.err`, `.tmp`, `.diff`,
  `.json` — deliberately *not* `.txt`, since `requirements.txt`/`CMakeLists.txt` are
  load-bearing manifests with that extension); and (d) under one of `_load_safe_redirect_dirs()`
  — the current project directory, `permissions.additionalDirectories` from your settings
  files, and the OS scratch dirs (`/tmp`, `/private/tmp`, `$TMPDIR`). An input redirect
  (`<`) is approved when its target is (a) literal text, (b) an absolute path (no relative
  paths), and (c) under a trusted directory as above — but *without* the extension
  restriction, since reading a file can't clobber it. That directory list only reuses places
  Claude Code is *already* trusted to read/write via Edit/Write; the hook doesn't grant a
  new capability, only skips a prompt for a command-line redirect into the same space. Any
  redirect that fails any one of those checks is refused outright.
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
- **Allow matching mirrors CC's own rule semantics.** `_allow_matches` treats `*` as a
  wildcard anywhere in the pattern — mid-string and repeated occurrences included (e.g.
  `Bash(gh api repos/*/contents/*)`), matching how Claude Code's own `Bash(...)` rules
  already work (settings.json already has rules like this). It also dequotes the rule text
  the same way bashlex dequotes a parsed command word (`_dequote_pattern`), so a rule
  written with literal quotes — typically because CC's own native matcher needs them to
  match the raw command text, e.g. `Bash(python3 -c "import yaml; ...")` — still lines up
  with the dequoted segment text it's compared against. This only ever matches what a
  human already wrote into an allow rule; it can't approve something CC's own matching on
  that same rule wouldn't.
- **Liberal deny matching + backstop.** `_deny_matches` uses the same glob semantics so it
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

## Compound command support

`for`, `if`/`elif`/`else`, `while`, and subshell/group (`(...)`/`{...}`) commands are
inspected rather than refused outright: every command that could possibly execute — across
every loop iteration and every branch — must match an allow rule, exactly like a plain
chain's segments. A standalone compound (no `&&`/`;` chaining it to anything else) is
eligible for approval on its own, since Claude Code's native matcher never handles these
shapes at all.

- **`for var in w1 w2 ...; do body; done`** — the iteration source must be either literal
  words, or a single command/process substitution (`$(cmd)`/backticks/`<(...)`) whose
  inner command is checked like any other substitution elsewhere in this hook. No separate
  "is this bounded" heuristic: if a user's own allow rules make both a broad enumerator and
  a broad reader approvable, a substitution-sourced loop combining them becomes approvable
  too — that's judged to be the user's own allow-rule risk, not a new capability this hook
  grants.
- **`if`/`elif`/`else`** — every condition and every branch's body must pass, all-or-nothing;
  one non-allowlisted or denied command in any branch refuses the whole thing.
- **`(cmd)` / `{ cmd; }`** — inspected exactly like a top-level chain.
- **`while cond; do body; done [< file]`** — `cond`/`body` checked like `if`. A trailing
  input redirect (`< file`) is approved only when the target is a literal absolute path
  under a trusted directory (project dir, `additionalDirectories`, OS scratch dirs) — the
  same trust boundary as the existing output-redirect carve-out, without the extension
  restriction (reading can't clobber a file).
- **Nesting** — a compound's body may contain one further nested compound; a compound
  nested inside that already-one-level-deep compound refuses the whole command.

**Not supported:**
- **`case`** — bashlex's grammar has case-pattern parsing explicitly stubbed out
  (`vendor/bashlex/parser.py`, `p_pattern` unconditionally raises `NotImplementedError`), so
  any `case` statement is unparseable and always falls back to a normal prompt, regardless of
  allow rules. Revisit only if a future bashlex release adds pattern support.
- **`until`/`select`** — out of scope; refused the same way any unrecognized construct is.
- **Functions and heredocs** — refused anywhere, including inside a compound body, same as
  at the top level.
- **Inline `VAR=val` assignments** — refused *unless* `val` is wholly a single command/process
  substitution; see "Variable assignment support" below.

See `docs/2026-07-21-compound-commands-design.md` for the full design rationale.

## Variable assignment support

`VAR=$(cmd)` (or `` VAR=`cmd` ``, or `VAR=<(cmd)`) is inspected rather than refused outright,
*only* when the entire value is one command/process substitution with no literal text mixed
in before or after it — the same all-or-nothing gate a `for` loop's iteration source already
uses. The substitution's inner command is then checked like any other segment: it must match
an allow rule and not match a deny rule, same as everywhere else in this hook. The assignment
itself counts as a top-level segment (like a plain command), so `r=$(git log -1) && echo "$r"`
can qualify as a chain on its own, not just inside a loop body.

- **Approved:** `r=$(git log --oneline -1) && echo "$r"` — the nested `git log` is checked;
  if it's allowlisted, the whole chain is.
- **Refused — no nested command to vet:** `x=bar && echo hi`. A plain literal has nothing for
  this hook to check, so it's left to a normal prompt, same as before this feature existed.
- **Refused — literal text riding along with the substitution:** `r=a$(git log -1)` or
  `r=$(git log -1)b`. Only the inner `git log` would be checked; the literal `a`/`b` folded
  into the same value would never be vetted at all, so the whole thing refuses.

**Accepted risk, on purpose.** This reopens a real gap the "every segment matches an
allow rule" model doesn't otherwise have: the captured value can flow into a *later*,
unrelated statement this hook has no way to tie back to "was produced by an approved
command." Two concrete shapes to be aware of if you lean on this:
- **Composition producing an effect no single rule was meant to permit** — e.g.
  `secret=$(gh api repos/*/contents/.env --jq .content | base64 -d)` followed by
  `echo "$secret"`: both `gh api repos/*/contents/*` and `base64 *` may be individually
  allowlisted for legitimate reasons, but chained through a captured variable they can
  decode and print a secrets file to the transcript.
- **Injection via untrusted captured data reinterpolated unquoted** — e.g.
  `title=$(gh pr view 42 --json title --jq .title)` followed by `git log --oneline $title`:
  a PR title is attacker-controlled text, and an unquoted later expansion lets it inject new
  arguments/commands into a statement this hook never re-checks.

This was a deliberate, informed tradeoff (not an oversight) — accepted after weighing those
scenarios against the friction of prompting on every `VAR=$(cmd)` chain. If that tradeoff ever
needs revisiting, the gate to tighten is `visitassignment`/`_is_single_substitution` in
`approve-allowlisted-chains.py`.

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
| `_allow_matches()`| Glob allow match (mirrors CC's own `Bash(...)` semantics). Extend *carefully* — looser matching risks over-approval. |
| `_deny_matches()` | Liberal deny match. Safe to widen; widening only adds prompts. |
| `_pattern_regex()`| Shared glob-to-regex conversion used by both match functions. |
| `_dequote_pattern()` | Strips quote characters from a rule's pattern text the same way bashlex dequotes a parsed command word. |
| `_KNOWN_BIN_DIRS` | Fixed set of directories a command name may be canonicalized from. Widen *carefully* — only add directories that exclusively hold trusted system/package-manager binaries. |
| `_canonicalize_command_word()` / `_canonicalize_segment()` | Strip a known bin-dir prefix from a segment's command name only, for allow/deny matching. |
| `_SAFE_REDIRECT_EXTENSIONS` | Extensions a real-file redirect target may end in. Widen *carefully* — only add extensions with no plausible critical-config use. |
| `_load_safe_redirect_dirs()` | Directories a real-file redirect target may live under: project dir + `additionalDirectories` from settings + OS scratch dirs. |
| `_under_safe_dir()` | `realpath`-resolves both the target and each safe dir before comparing, so symlinked prefixes (e.g. macOS `/tmp` -> `/private/tmp`) can't cause a false mismatch either way. |
| `_MAX_COMPOUND_DEPTH` | Nesting cap for compound commands (1 = top-level only, 2 = one nested level allowed). |
| `_SUPPORTED_COMPOUND_KEYWORDS` | Which compound keywords (`for`/`if`/`while`) this hook walks into; subshell/group are handled unconditionally alongside it. Extend *carefully* -- adding a keyword here means its body/conditions get the same allow/deny check as a plain chain, with no further safety net. |
| `_is_single_substitution()` | True iff a word/assignment's value is wholly one command/process substitution, no literal text mixed in. Shared gate for `visitfor`'s iteration source and `visitassignment`'s `VAR=$(cmd)` value. |
| `_ChainInspector` | bashlex AST visitor: collects segments (recursing into substitutions), flags unsafe constructs, and gates real-file redirects on `visitredirect`, `visitfor`, `visitassignment`, and `visitnodeend` per the safety model above. |
| `_inspect()`      | Parse + walk → `(segments, top_level_count, had_compound, reason)`. Takes an optional `safe_dirs` list. |
| `decide()`        | End-to-end `(command, allow, deny, safe_dirs=None) -> bool`. `safe_dirs=None` loads live settings/env; pass a fixed list for deterministic tests. |

When you change any of these, **add a case** to `test_approve_allowlisted_chains.py` (and,
for a quick built-in check, to `_selftest()` in the script). Golden rule for
`_allow_matches`: if you're unsure whether a change could match something CC wouldn't,
don't — bail instead.

## Known limitations (all fail *safe* — toward prompting)

- **Relative-path real-file redirects always refuse**, even with `safe_dirs` configured
  and a safe extension — resolving them correctly would require knowing the effective cwd,
  which an earlier `cd` in the same chain could have changed. Use an absolute path.
- **bash grammar, not zsh.** Exotic zsh-only syntax may not parse → bail → prompt.
- **`~/.claude/settings.local.json` is not read** (uncertain whether CC applies it to
  permissions; omitting it only makes the hook more conservative).
- **Path canonicalization only recognizes a fixed list of bin directories**
  (`_KNOWN_BIN_DIRS`) — an absolute path elsewhere (e.g. a project-local
  `node_modules/.bin/`, or a Homebrew Cellar path) is left unchanged and just prompts, same
  as before this feature existed.
- **`case` statements are always refused** — not a design choice, a vendored-dependency
  limit (see "Compound command support" above). No configuration changes this.
- **Compound nesting deeper than one extra level always refuses**, regardless of whether
  every command inside would otherwise be allowlisted.

## Files

Everything is self-contained in `~/.claude/hooks/approve-allowlisted-chains/`:

```
approve-allowlisted-chains.py          the hook + --selftest + --check
README.md                              this file
test_approve_allowlisted_chains.py     unit suite
vendor/                                vendored bashlex
```
