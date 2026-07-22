# Compound command support — design

Status: approved, not yet implemented. Extends `approve-allowlisted-chains.py`'s "Proposed
extension: compound commands" section in `README.md`, resolving the gray areas raised there.

## Goal

Today the hook refuses `for`/`while`/`if`/`case`/subshell/group outright (see `visitcompound`
in `approve-allowlisted-chains.py`). This spec extends it to approve these constructs when —
and only when — every command that could possibly execute, across every branch and every
iteration, is already allowlisted. Nothing here loosens the existing safety model for plain
chains; it only widens what shapes the same allow/deny check is applied to.

## Scope

In scope: `for`, `if`/`elif`/`else`, subshell/group (`(...)`/`{...}`), `while`.
One level of nesting (a compound body may contain one further nested compound).

Out of scope (stays refused, same as today): `case`, `until`, `select`, nesting two or
more levels deep, functions, heredocs, inline `VAR=val` assignments.

**`case` is blocked on the vendored dependency, not a design choice:** bashlex's grammar
has `case`-pattern parsing explicitly stubbed out (`vendor/bashlex/parser.py`,
`p_pattern` calls `handleNotImplemented(p, 'pattern')` unconditionally) — any
`case ... in a) ...) esac` raises `NotImplementedError`, which `_inspect()` already
catches and treats as "not parseable" (falls back to a normal prompt). No amount of
visitor code on our side can approve a construct bashlex never builds an AST for. Revisit
only if a future bashlex release (or a patched vendor copy) adds pattern support — patching
the vendored grammar ourselves was considered and rejected as a disproportionately risky,
high-maintenance way to unblock one construct.

## 1. Gate logic

The existing gate ("approve only when ≥2 top-level segments, or exactly 1 whose only
obstacle was path-canonicalization") exists because Claude Code's native matcher already
auto-approves an ordinary single simple command on its own — the hook only needs to cover
shapes CC's native matcher misses.

Compound commands break that assumption: CC's native matcher never handles a
`for`/`if`/`case`/subshell/`while`, not even alone, standalone or chained. New rule:

- A top-level item is either **(a)** a simple command (checked as today — raw or
  canonicalized text against allow/deny), or **(b)** a compound command, checked recursively
  per Section 2.
- Approve iff every top-level item passes its check, **and** at least one of: there are ≥2
  top-level items, **or** the single top-level item is a compound, **or** it's the existing
  lone-canonicalized-path case.
- Consequence: a bare standalone compound (e.g. just one `for` loop, nothing chained to it)
  is now eligible for approval on its own.

## 2. Per-construct safety rules

"Safe" means: collect every simple command that could possibly execute across all
branches/iterations, and require every one to match an allow rule and none to match a deny
rule — the same allow/deny check used today for plain chains, applied to more commands.

- **`for var in w1 w2 ...; do body; done`** — the iteration source must be either literal
  words, or a single command substitution (`$(cmd)` / backticks) whose inner command is
  checked exactly like any other substitution elsewhere in the hook: same allow-rule match,
  no separate "is this bounded" heuristic. (Accepted consequence, confirmed: if a user has
  both a broad enumerator like `find *` and a broad reader like `cat *` on their own
  allowlist, a substitution-sourced loop combining them becomes approvable. That's judged
  to be the user's own allow-rule risk, not a new capability the hook grants — see README's
  "must never" example 4, which is superseded by this decision.) Every command in `body` is
  checked once — its text is static; only `var`'s value changes across iterations, and that
  value only ever appears as literal argument *text*, never as the command word (a command
  word that's itself a variable expansion, e.g. `$cmd`, stays literal text like `"$cmd
  file"` in the segment and simply won't match a sane allow pattern such as `ls *` — no
  special-casing needed).
- **`if cond1; then body1; elif cond2; then body2; else body3; fi`** — every `cond*`
  actually executes to pick a branch, so conditions are checked too, alongside every
  branch's body. All-or-nothing across every condition and every branch: one non-allowlisted
  or denied command anywhere refuses the whole thing.
- **`(cmd)` / `{ cmd; }`** (subshell/group for scoping) — contents checked exactly like a
  top-level chain today.
- **`while cond; do body; done [< file]`** — `cond`/`body` checked like `if`. The trailing
  `< file` is covered by Section 3.
- **Nesting** — a compound's body may contain **one further nested compound**, inspected
  with these same rules recursively. A compound nested inside that already-one-level-deep
  compound refuses the whole command.

## 3. Input redirects

Today every input redirect (`<`) is refused outright, no exception. Supporting
`while ... done < file` needs a narrow carve-out, mirroring the existing output-redirect
logic but without the extension check (reading can't clobber a file, so there's no
manifest-file risk to guard against):

- An input redirect is approved only when its target is **literal text** (no
  `$VAR`/`$(...)`/backticks) and an **absolute path** under one of the existing `safe_dirs`
  (project dir, `additionalDirectories`, OS scratch dirs) — same trust boundary already used
  for output redirects, minus the extension restriction. Anything else (relative path,
  dynamic path, outside safe dirs) refuses the whole command.

## What stays refused (unchanged)

- Any branch/iteration body containing even one non-allowlisted or denied command.
- `case` — unparseable by the vendored bashlex (see Scope); always falls through to a
  normal prompt regardless of allow rules.
- `until`/`select` — treated as an unrecognized construct, same as before this feature.
- Anything nested two or more levels deep.
- Real-file redirects that fail the literal/absolute/safe-dir checks, in any branch.
- Functions, heredocs, inline `VAR=val` assignments — anywhere, including inside a compound
  body.

## Testing plan

Extend `test_approve_allowlisted_chains.py` and `_selftest()` with cases covering:

- `for` with a literal word list; `for` with a command-substitution source.
- `if`/`elif`/`else` where every branch passes; `if` with one denied/non-allowlisted branch.
- `case` is refused outright (parse failure), confirming it safely falls back to a prompt.
- Subshell/group used for scoping.
- `while` with a safe input redirect; `while` with an unsafe (relative/dynamic/outside
  safe-dir) input redirect.
- One level of nesting approved; two levels of nesting refused.
- A standalone compound with nothing chained to it (tests the Section 1 gate change).
- A `for`/`while` whose body's command word is a bare variable expansion (confirms it fails
  to match any allow rule rather than being specially detected/refused).

`README.md`'s "Proposed extension" section is rewritten to document actual behavior instead
of a draft, once implemented.
