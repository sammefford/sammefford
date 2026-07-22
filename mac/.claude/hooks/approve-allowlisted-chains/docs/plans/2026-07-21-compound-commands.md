# Compound Command Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `approve-allowlisted-chains.py` so `for`, `if`/`elif`/`else`, `while`, and
subshell/group (`(...)`/`{...}`) commands can be auto-approved when every command that could
execute inside them is already allowlisted — today they're refused outright.

**Architecture:** The hook already walks a bashlex AST with a `bashlex.ast.nodevisitor`
subclass (`_ChainInspector`) that collects every simple-command segment and refuses on unsafe
constructs. This plan replaces the blanket `visitcompound` refusal with real inspection:
depth-tracked recursion into `for`/`if`/`while`/subshell/group bodies, reusing the exact same
allow/deny check `decide()` already applies to plain chains. `case` is excluded — see
Global Constraints.

**Tech Stack:** Python 3 stdlib + vendored `bashlex` (already present in `vendor/`). Tests via
`pytest` / the standalone runner in `test_approve_allowlisted_chains.py`.

## Global Constraints

- Spec: `../2026-07-21-compound-commands-design.md` (read it first — this plan implements it).
- A git repository was initialized scoped to this hook's directory specifically for this
  implementation effort (`~/.claude` itself is still not a repo). Commit steps below apply
  normally: commit at the end of each task from the current working directory.
- `case` is **out of scope, permanently, for this plan**: bashlex's grammar has case-pattern
  parsing stubbed out (`vendor/bashlex/parser.py:398-401`, `p_pattern` always calls
  `handleNotImplemented`), so any `case` statement raises `NotImplementedError` and is already
  caught by `_inspect`'s existing exception handling, falling back to a normal prompt. Do not
  attempt to patch the vendored parser.
- `until`/`select` stay refused — not in scope.
- Nesting is capped at exactly one extra level (a compound inside a compound is fine; a
  compound inside that is refused).
- Follow the existing file's style: `from __future__ import annotations`, `list[str] | None`
  syntax, one flat script (do not split into multiple modules — the file stays well under a
  size where that would be warranted).
- Never loosen `_allow_matches`/`_deny_matches`/`_canonicalize_*` semantics — this plan only
  widens *which shapes* those functions get applied to, never how they match.
- After every task, run the full suite and confirm 100% pass before moving on, from this
  directory: `pytest test_approve_allowlisted_chains.py -q`

## Key bashlex AST facts (verified against the vendored copy — you don't need to rediscover these)

- A compound command (`for`/`if`/`while`/subshell/group) always parses to a `compound` node
  with two attributes: `.list` (its children) and `.redirects` (e.g. the `< file` after a
  `while ... done`).
- For `for`/`if`/`while`, `.list` is `[node]` where `node.kind` is `"for"`/`"if"`/`"while"` and
  `node.parts` is a flat mix of `reservedword` nodes (`for`, `in`, `;`, `do`, `done`, `then`,
  `elif`, `else`, `fi`, etc.), `word` nodes, and `list` nodes (conditions and bodies).
- For a subshell/group, `.list` is `[reservedword('(' or '{'), <command-or-list>, reservedword(')' or '}')]`
  — the middle element is a bare `command` node if there's only one command inside, or a
  `list` node if there's more than one (e.g. joined by `&&`).
- `bashlex.ast.nodevisitor.visit()` already auto-recurses into a node's children whenever the
  corresponding `visit<kind>` method returns `None` (or a truthy value) — you do **not** need
  to manually call `self.visit(child)` for `if`/`while` bodies or subshell/group contents; the
  base class does it once you return `None` from `visitcompound`. `for` needs one exception
  (see Task 2) because its iteration-source words need shape validation before letting them
  through.
- `visitnodeend(n)` is called once per node, right after all of that node's children have
  finished being visited — this is where compound-nesting depth gets decremented, so it stays
  balanced even when a node's own `visit<kind>` method returned `False` to refuse early.

---

### Task 1: Gate logic + depth tracking + subshell/group support

**Files:**
- Modify: `approve-allowlisted-chains.py` (`_ChainInspector.__init__`, `visitcompound`,
  `visitcommand`, `_inspect`, `decide`, `_check`; add `visitnodeend`; add two new module
  constants near `_KNOWN_BIN_DIRS`)
- Test: `test_approve_allowlisted_chains.py`

**Interfaces:**
- Produces: `_inspect(command, safe_dirs=None) -> (segments: list[str] | None, top_level_count: int, had_compound: bool, reason: str | None)` — a **new 4th-position `had_compound`** field (previously 3-tuple `(segments, top_level_count, reason)`). Every existing caller/test that unpacks this tuple must be updated.
- Produces: `_ChainInspector.had_compound: bool` and `_ChainInspector._compound_depth: int` instance attributes.
- Produces: module constants `_MAX_COMPOUND_DEPTH = 2` and `_SUPPORTED_COMPOUND_KEYWORDS: frozenset[str]` (empty in this task; later tasks add `"for"`/`"if"`/`"while"` to it one at a time).
- Consumes: existing `_canonicalize_segment`, `_allow_matches`, `_deny_matches` (unchanged).

- [ ] **Step 1: Update existing tests for the new 4-tuple `_inspect` return and the retired blanket-refusal test**

In `test_approve_allowlisted_chains.py`, apply these five edits (unpacking a 4th value,
`had_compound`, and asserting it's `False` since none of these commands contain a compound):

```python
def test_inspect_simple_chain_splits_and_drops_redirects():
    segments, top_level_count, had_compound, reason = aac._inspect(
        "cd x && git log -1 2>&1; echo hi | grep h"
    )
    assert reason is None
    assert segments == ["cd x", "git log -1", "echo hi", "grep h"]
    assert top_level_count == 4
    assert had_compound is False


def test_inspect_recurses_into_command_substitution():
    # The substitution's inner command becomes an extra segment, not an outright refusal.
    segments, top_level_count, had_compound, reason = aac._inspect(
        'echo "$(git rev-parse HEAD)" && echo ok'
    )
    assert reason is None
    # bashlex strips the surrounding quotes from the extracted word text.
    assert segments == ["echo $(git rev-parse HEAD)", "git rev-parse HEAD", "echo ok"]
    assert top_level_count == 2  # the nested segment doesn't count toward the chain gate
    assert had_compound is False


def test_inspect_recurses_into_backticks_too():
    segments, top_level_count, had_compound, reason = aac._inspect("echo `whoami`")
    assert reason is None
    assert segments == ["echo `whoami`", "whoami"]
    assert top_level_count == 1  # single top-level command; substitution doesn't make a chain
    assert had_compound is False


def test_inspect_recurses_into_process_substitution():
    segments, top_level_count, had_compound, reason = aac._inspect(
        "diff <(git log) <(git fetch)"
    )
    assert reason is None
    assert segments == ["diff <(git log) <(git fetch)", "git log", "git fetch"]
    assert top_level_count == 1  # one top-level command; process substitution isn't a chain
    assert had_compound is False


def test_inspect_keeps_quoted_operators_inside_one_command():
    # The ';' and '&&' are inside quotes -> a single echo argument, not splits.
    segments, _, had_compound, reason = aac._inspect('echo "a; rm -rf ~ && reboot"')
    assert reason is None
    assert segments == ["echo a; rm -rf ~ && reboot"]
    assert had_compound is False
```

Replace `test_inspect_refuses_compound_and_subshell` (the subshell half of this assertion is
about to become false once this task lands — subshells will be inspected, not refused
outright — but `for` isn't implemented until Task 2, so it keeps refusing here):

```python
def test_inspect_refuses_unimplemented_compound_shapes():
    # 'for' isn't supported until a later task in this plan; still refused here.
    assert aac._inspect("for d in a b; do echo $d; done")[0] is None
```

Add new tests (these will fail until Task 1's implementation lands):

```python
def test_inspect_approves_subshell_grouping_when_body_is_safe():
    segments, top_level_count, had_compound, reason = aac._inspect(
        "(cd ~/dev/x && git log --oneline -1)"
    )
    assert reason is None
    assert segments == ["cd ~/dev/x", "git log --oneline -1"]
    assert top_level_count == 1
    assert had_compound is True


def test_inspect_approves_brace_group_when_body_is_safe():
    segments, top_level_count, had_compound, reason = aac._inspect("{ echo hi; echo bye; }")
    assert reason is None
    assert segments == ["echo hi", "echo bye"]
    assert top_level_count == 1
    assert had_compound is True


def test_inspect_approves_one_level_of_nested_subshell():
    segments, _, _, reason = aac._inspect("(echo hi && (echo mid))")
    assert reason is None
    assert segments == ["echo hi", "echo mid"]


def test_inspect_refuses_two_levels_of_nested_subshell():
    assert aac._inspect("(echo hi && (echo mid && (echo deep)))")[0] is None


def test_inspect_refuses_until_loop():
    # 'until' is a recognized bashlex node kind but deliberately not in
    # _SUPPORTED_COMPOUND_KEYWORDS -- out of scope for this plan.
    assert aac._inspect("until false; do echo x; done")[0] is None


def test_inspect_refuses_file_redirect_on_a_command_inside_a_compound_body():
    # Redirect checking (visitredirect) is now reachable from inside a compound body for
    # the first time -- confirm it still refuses a plain unsafe redirect there, exactly
    # as it always has at the top level.
    assert aac._inspect("(echo hi > out.txt)")[0] is None


def test_decide_approves_standalone_subshell_when_body_allowlisted():
    # No chaining at all -- a bare compound is now eligible for approval on its own,
    # since Claude Code's native matcher never handles compounds, chained or not.
    assert aac.decide("(cd ~/dev/x && git log --oneline -1)", ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_standalone_subshell_with_unallowlisted_command():
    assert not aac.decide("(cd ~/dev/x && git status --short)", ALLOW, DENY, SAFE_DIRS)


def test_decide_approves_subshell_chained_with_simple_command():
    assert aac.decide(
        "(cd ~/dev/x && git log --oneline -1) && echo done", ALLOW, DENY, SAFE_DIRS
    )
```

- [ ] **Step 2: Run the suite to confirm the expected failures**

Run: `pytest test_approve_allowlisted_chains.py -q`
Expected: FAIL on the new/changed tests (`ValueError: not enough values to unpack` for the
4-tuple ones; assertion failures for the subshell/group/nesting ones — `(echo hi)`-shaped
commands currently return `None`). Tests unrelated to `_inspect`'s tuple shape or compound
handling still pass.

- [ ] **Step 3: Add the two module constants**

In `approve-allowlisted-chains.py`, right after the `_KNOWN_BIN_DIRS` definition (around line
203), add:

```python
# Nesting cap for compound commands: 1 = the top-level compound itself, 2 = one further
# nested compound inside its body. Anything deeper refuses outright -- see design doc.
_MAX_COMPOUND_DEPTH = 2

# Compound-command keywords this hook is willing to walk into (see design doc). Empty until
# later tasks in this plan add "for"/"if"/"while" one at a time. Subshell/group (a bare "("
# or "{" as the compound's first element) are supported unconditionally below, not gated by
# this set, since they carry no keyword node of their own.
_SUPPORTED_COMPOUND_KEYWORDS: frozenset[str] = frozenset()
```

- [ ] **Step 4: Rewrite `_ChainInspector.__init__`, `visitcompound`, add `visitnodeend`, update `visitcommand`**

Replace the `__init__` method:

```python
    def __init__(self, safe_dirs: list[str] | None = None) -> None:
        self.commands: list[str] = []
        self.top_level_commands = 0
        self.had_compound = False
        self._subst_depth = 0
        self._compound_depth = 0
        self._safe_dirs = safe_dirs or []
        self.reason: str | None = None
```

Replace the current `visitcompound` (which unconditionally refuses) with:

```python
        def visitcompound(self, n, list, redirects) -> bool | None:
            """Compound commands (for/if/while, subshell/group) are inspected rather than
            refused outright: walk into the construct and let the base class's own
            recursion (or visitfor, added by a later task) collect every command that
            could execute, subject to the same allow/deny check as a plain chain. Refuses
            outright on an unsupported shape (case is unparseable by bashlex and never
            reaches here; until/select are unsupported by this hook) or on nesting beyond
            one extra level deep.

            Depth is incremented unconditionally before any check, so visitnodeend's
            decrement (which always runs) stays balanced even on early refusal. A
            top-level compound counts as exactly one top-level segment for decide()'s
            chain gate -- tracked via `had_compound`/`top_level_commands` here, not per
            inner command (see visitcommand's own gating)."""
            self._compound_depth += 1
            if self.reason is not None:
                return False
            if self._compound_depth > _MAX_COMPOUND_DEPTH:
                self._refuse(
                    "compound command nested too deeply (only one nested level is supported)"
                )
                return False
            inner = list[0] if list else None
            is_group = (
                inner is not None
                and inner.kind == "reservedword"
                and inner.word in ("(", "{")
            )
            is_supported_keyword = inner is not None and inner.kind in _SUPPORTED_COMPOUND_KEYWORDS
            if inner is None or not (is_group or is_supported_keyword):
                shape = inner.kind if inner is not None else "empty"
                self._refuse(f"unsupported compound shape ({shape})")
                return False
            if self._compound_depth == 1 and self._subst_depth == 0:
                self.top_level_commands += 1
                self.had_compound = True
            return None  # let the base class recurse into `list` and `redirects`

        def visitnodeend(self, n) -> None:
            if n.kind == "compound":
                self._compound_depth -= 1
```

Update `visitcommand`'s top-level-counting condition (add the `and self._compound_depth == 0`
clause — commands inside a compound's body still get collected into `self.commands`, just no
longer separately counted as top-level segments; the compound itself was already counted once,
above):

```python
        def visitcommand(self, n, parts) -> None:
            words = [p.word for p in parts if p.kind == "word"]
            if words:
                self.commands.append(" ".join(words))
                if self._subst_depth == 0 and self._compound_depth == 0:
                    self.top_level_commands += 1
```

- [ ] **Step 5: Update `_inspect` to return the 4-tuple**

```python
def _inspect(
    command: str, safe_dirs: list[str] | None = None
) -> tuple[list[str] | None, int, bool, str | None]:
    """Parse `command` and return (segments, top_level_count, had_compound, None) for a
    safe command, or (None, 0, False, reason) when it cannot be safely auto-approved.
    `segments` includes commands nested inside a substitution or a compound body;
    `top_level_count` counts only top-level items (a plain command, or an entire compound
    counted once regardless of how many commands are inside it) -- see decide()'s gate
    logic. `had_compound` is True iff at least one top-level item was a compound command
    (for/if/while/subshell/group), used to decide whether a lone top-level item is
    eligible for approval on its own (a compound always is; a plain command only is via
    the existing path-canonicalization case).

    `safe_dirs` (default none) bounds which absolute paths a real-file redirect may
    target; see `_ChainInspector`."""
    if bashlex is None:
        return None, 0, False, "bashlex unavailable"
    try:
        trees = bashlex.parse(command)
    except (bashlex.errors.ParsingError, NotImplementedError):
        return None, 0, False, "not parseable as a simple command chain"
    except Exception as exc:  # bashlex can raise assorted errors on exotic input
        return None, 0, False, f"parse error ({type(exc).__name__})"
    inspector = _ChainInspector(safe_dirs)
    try:
        for tree in trees:
            inspector.visit(tree)
    except Exception as exc:
        return None, 0, False, f"walk error ({type(exc).__name__})"
    if inspector.reason is not None:
        return None, 0, False, inspector.reason
    return inspector.commands, inspector.top_level_commands, inspector.had_compound, None
```

- [ ] **Step 6: Update `decide()`'s gate logic**

```python
def decide(
    command: str, allow: list[str], deny: list[str], safe_dirs: list[str] | None = None
) -> bool:
    """True iff `command` is safely approvable: either a plain chain of >= 2 top-level
    items, a single top-level item that is a compound command (for/if/while/subshell/
    group -- Claude Code's native matcher never handles these, chained or alone), or a
    single top-level plain command whose only obstacle was an absolute path into a known
    bin directory (see `_canonicalize_segment`) -- and, in every case, every underlying
    command (including any nested inside a substitution or a compound body, checked in
    both its raw and canonicalized form) matches an allow rule while none matches a deny
    rule.

    `safe_dirs`: directories a real-file redirect may target. Defaults to
    `_load_safe_redirect_dirs()` (live settings/env) when not given -- callers that need
    deterministic results (tests) should pass a fixed list explicitly."""
    if safe_dirs is None:
        safe_dirs = _load_safe_redirect_dirs()
    segments, top_level_count, had_compound, _ = _inspect(command, safe_dirs)
    if not segments or not allow:
        return False
    is_chain = top_level_count >= 2
    is_lone_compound = top_level_count == 1 and had_compound
    is_lone_path_command = (
        top_level_count == 1
        and not had_compound
        and _canonicalize_segment(segments[0]) != segments[0]
    )
    if not (is_chain or is_lone_compound or is_lone_path_command):
        return False
    for segment in segments:
        canon = _canonicalize_segment(segment)
        candidates = (segment,) if canon == segment else (segment, canon)
        if any(_deny_matches(c, pattern) for c in candidates for pattern in deny):
            return False
        if not any(_allow_matches(c, pattern) for c in candidates for pattern in allow):
            return False
    return True
```

- [ ] **Step 7: Update `_check()` for the 4-tuple and the new lone-compound case**

```python
def _check() -> int:
    """Diagnostic: read a raw command from stdin and explain the decision against the
    real settings. Usage: approve-allowlisted-chains.py --check < cmd.txt"""
    command = sys.stdin.read().strip()
    allow, deny = _load_rules()
    safe_dirs = _load_safe_redirect_dirs()
    verdict = decide(command, allow, deny, safe_dirs)
    print(f"decision: {'AUTO-APPROVE (no prompt)' if verdict else 'DEFER to normal prompt'}\n")
    segments, top_level_count, had_compound, reason = _inspect(command, safe_dirs)
    if segments is None:
        print(f"refused: {reason}")
        return 0
    is_lone_compound = top_level_count == 1 and had_compound
    is_lone_path_command = (
        top_level_count == 1
        and not had_compound
        and _canonicalize_segment(segments[0]) != segments[0]
    )
    if top_level_count < 2 and not is_lone_path_command and not is_lone_compound:
        print(f"deferred: not a chain ({top_level_count} top-level segment)")
        return 0
    for segment in segments:
        canon = _canonicalize_segment(segment)
        candidates = (segment,) if canon == segment else (segment, canon)
        denied = next((p for c in candidates for p in deny if _deny_matches(c, p)), None)
        allowed = next((p for c in candidates for p in allow if _allow_matches(c, p)), None)
        if denied:
            tag = f"DENIED by Bash({denied})"
        elif allowed:
            tag = f"ok via Bash({allowed})"
        else:
            tag = "NO MATCHING ALLOW RULE"
        shown = segment if canon == segment else f"{segment}  [canonicalized: {canon}]"
        mark = "ok  " if allowed and not denied else "FAIL"
        print(f"  [{mark}] {shown}   -> {tag}")
    return 0
```

- [ ] **Step 8: Run the full suite and confirm everything passes**

Run: `pytest test_approve_allowlisted_chains.py -q`
Expected: all tests pass (`N/N passed` or pytest's equivalent).

- [ ] **Step 9: Run the built-in selftest too, as a sanity check (no assertions changed yet, just confirming nothing broke)**

Run: `python3 approve-allowlisted-chains.py --selftest`
Expected: `N/N passed` — same count as before this task (the fixture cases list isn't touched
until Task 5).

---

### Task 2: `for`-loop support

**Files:**
- Modify: `approve-allowlisted-chains.py` (`_ChainInspector`: add `visitfor`; update
  `_SUPPORTED_COMPOUND_KEYWORDS`)
- Test: `test_approve_allowlisted_chains.py`

**Interfaces:**
- Consumes: `_SUPPORTED_COMPOUND_KEYWORDS` (Task 1), `visitcompound`/`visitcommandsubstitution`/`visitprocesssubstitution` (existing/Task 1).
- Produces: `_ChainInspector.visitfor(self, n, parts) -> bool | None`.

- [ ] **Step 1: Remove the now-outdated for-loop assertion from `test_decide_rejects_dangerous_constructs`**

```python
def test_decide_rejects_dangerous_constructs():
    assert not aac.decide("echo $(whoami) && echo hi", ALLOW, DENY, SAFE_DIRS)  # whoami isn't allowlisted
    assert not aac.decide("echo hi && git log > out.txt", ALLOW, DENY, SAFE_DIRS)
    assert not aac.decide("FOO=bar git log && echo hi", ALLOW, DENY, SAFE_DIRS)
```

(The `for d in a b; do echo $d; done` line is removed — a bare `for` loop is no longer
unconditionally dangerous; its allowlist-dependent behavior is covered by the new tests below.)

- [ ] **Step 2: Add failing tests**

```python
def test_inspect_approves_for_loop_with_literal_word_list():
    segments, top_level_count, had_compound, reason = aac._inspect(
        "for r in dev stage prod; do git log --oneline -1 origin/$r; done"
    )
    assert reason is None
    assert segments == ["git log --oneline -1 origin/$r"]
    assert top_level_count == 1
    assert had_compound is True


def test_inspect_approves_for_loop_with_command_substitution_source():
    segments, top_level_count, had_compound, reason = aac._inspect(
        "for f in $(git log --oneline -3); do grep x $f; done"
    )
    assert reason is None
    assert segments == ["git log --oneline -3", "grep x $f"]
    assert top_level_count == 1
    assert had_compound is True


def test_inspect_refuses_for_loop_without_in_clause():
    assert aac._inspect("for x; do echo $x; done")[0] is None


def test_inspect_refuses_for_loop_with_mixed_literal_and_substitution_source():
    assert aac._inspect("for f in a $(git log -1); do echo $f; done")[0] is None


def test_inspect_refuses_for_loop_with_variable_iteration_source():
    # A bare $VAR as the source isn't a literal word list or a substitution -- refuse
    # rather than guess what it expands to.
    assert aac._inspect("for f in $FILES; do echo $f; done")[0] is None


def test_decide_approves_for_loop_over_literal_list_when_body_allowlisted():
    cmd = "for r in dev stage prod; do git log --oneline -1 origin/$r; done"
    assert aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_for_loop_with_unallowlisted_body_command():
    cmd = "for r in dev stage prod; do git status --short; done"
    assert not aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)


def test_decide_approves_for_loop_over_substitution_when_both_allowlisted():
    cmd = "for f in $(git log --oneline -3); do grep x $f; done"
    assert aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_for_loop_whose_command_word_is_a_bare_variable():
    # `$c` as the command word stays literal text in the segment ("$c file") and simply
    # won't match any sane allow pattern -- no special-casing needed (design doc Section 2).
    cmd = "for c in ls cat; do $c file; done"
    assert not aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)
```

- [ ] **Step 3: Run to verify the new/changed tests fail**

Run: `pytest test_approve_allowlisted_chains.py -q`
Expected: FAIL on all the new `for`-loop tests above (still refused as "unsupported compound
shape (for)"), and `test_decide_rejects_dangerous_constructs` still passes (nothing in it
references `for` anymore).

- [ ] **Step 4: Add `visitfor` and enable `"for"` in the supported-keywords set**

Add `"for"` to the constant defined in Task 1:

```python
_SUPPORTED_COMPOUND_KEYWORDS: frozenset[str] = frozenset({"for"})
```

Add this method to `_ChainInspector` (near `visitcommand`):

```python
        def visitfor(self, n, parts) -> bool | None:
            """`for var in w1 w2 ...; do body; done`. The iteration source (after `in`)
            must be either all-literal words, or a single command substitution/backtick/
            process substitution spanning the entire word -- checked the same way any
            other substitution is (visitcommandsubstitution/visitprocesssubstitution), no
            separate "is this bounded" heuristic (design doc Section 2). Returning None
            lets the base class recurse through every part, including the item words
            (triggering nested-substitution handling when present) and the body's `list`
            node (collecting its commands via visitcommand)."""
            if self.reason is not None:
                return False
            in_idx = next(
                (i for i, p in enumerate(parts) if p.kind == "reservedword" and p.word == "in"),
                None,
            )
            if in_idx is None:
                self._refuse("for loop without an explicit 'in' word list is not supported")
                return False
            items = []
            for p in parts[in_idx + 1 :]:
                if p.kind != "word":
                    break
                items.append(p)
            if not items:
                self._refuse("for loop has no iteration words")
                return False
            all_literal = all(not w.parts for w in items)
            single_subst = (
                len(items) == 1
                and len(items[0].parts) == 1
                and items[0].parts[0].kind in ("commandsubstitution", "processsubstitution")
                and (
                    (items[0].word.startswith("$(") and items[0].word.endswith(")"))
                    or (items[0].word.startswith("`") and items[0].word.endswith("`"))
                    or (items[0].word.startswith("<(") and items[0].word.endswith(")"))
                )
            )
            if not (all_literal or single_subst):
                self._refuse(
                    "for loop iteration source must be a literal word list or a single "
                    "command substitution"
                )
                return False
            return None
```

- [ ] **Step 5: Run the full suite and confirm everything passes**

Run: `pytest test_approve_allowlisted_chains.py -q`
Expected: all tests pass.

---

### Task 3: `if`/`elif`/`else` support

**Files:**
- Modify: `approve-allowlisted-chains.py` (update `_SUPPORTED_COMPOUND_KEYWORDS` only — no new
  visitor method needed, see below)
- Test: `test_approve_allowlisted_chains.py`

**Interfaces:**
- Consumes: `_SUPPORTED_COMPOUND_KEYWORDS`, `visitcompound` (Task 1).
- Produces: nothing new — `if`'s conditions and every branch's body are `list` nodes inside
  `n.parts`, and the base class's default (no-op) `visitif` already lets the base-class
  recursion walk into all of them once `visitcompound` returns `None`. This was verified
  against the vendored bashlex directly (see plan header) before writing this task.

- [ ] **Step 1: Add failing tests**

```python
def test_inspect_approves_if_else_when_every_branch_is_safe():
    segments, top_level_count, had_compound, reason = aac._inspect(
        "if git log -1; then echo clean; else echo dirty; fi"
    )
    assert reason is None
    assert segments == ["git log -1", "echo clean", "echo dirty"]
    assert top_level_count == 1
    assert had_compound is True


def test_inspect_approves_if_elif_else_chain():
    segments, _, _, reason = aac._inspect(
        "if git log -1; then echo a; elif git fetch origin; then echo b; else echo c; fi"
    )
    assert reason is None
    assert segments == ["git log -1", "echo a", "git fetch origin", "echo b", "echo c"]


def test_inspect_approves_one_level_nested_subshell_inside_if():
    segments, _, _, reason = aac._inspect("if true; then (echo hi && echo bye); fi")
    assert reason is None
    assert "echo hi" in segments and "echo bye" in segments


def test_decide_approves_if_else_when_every_branch_and_condition_allowlisted():
    cmd = "if git log -1; then echo clean; else echo dirty; fi"
    assert aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_if_else_with_one_unallowlisted_branch():
    # all-or-nothing across every branch: the then-branch passes, but the else branch's
    # command doesn't -- the whole compound must still refuse.
    cmd = "if git log -1; then echo clean; else git status --short; fi"
    assert not aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_if_with_unallowlisted_condition():
    cmd = "if git status --short; then echo clean; fi"
    assert not aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)
```

- [ ] **Step 2: Run to verify these fail**

Run: `pytest test_approve_allowlisted_chains.py -q`
Expected: FAIL on all new `if` tests (still refused as "unsupported compound shape (if)").

- [ ] **Step 3: Enable `"if"` in the supported-keywords set**

```python
_SUPPORTED_COMPOUND_KEYWORDS: frozenset[str] = frozenset({"for", "if"})
```

- [ ] **Step 4: Run the full suite and confirm everything passes**

Run: `pytest test_approve_allowlisted_chains.py -q`
Expected: all tests pass. If any `if`-related test still fails, re-check the exact `.parts`
shape with a throwaway script (`bashlex.parse("if a; then b; fi")`, dump node kinds) before
changing any allow/deny logic — the AST facts in this plan's header were verified directly
against the vendored bashlex copy, so a mismatch likely means a different bashlex version is
installed.

---

### Task 4: `while`-loop support + input-redirect carve-out

**Files:**
- Modify: `approve-allowlisted-chains.py` (`visitredirect`; update `_SUPPORTED_COMPOUND_KEYWORDS`)
- Test: `test_approve_allowlisted_chains.py` (also add `"read *"` to the module-level `ALLOW` fixture)

**Interfaces:**
- Consumes: `_under_safe_dir`, `_load_safe_redirect_dirs`, `_SAFE_REDIRECT_EXTENSIONS` (existing).
- Produces: `visitredirect` now also approves a narrow class of input redirects (`<`).

- [ ] **Step 1: Add `"read *"` to the test file's shared `ALLOW` fixture**

`while read -r line; do ...; done` needs `read` allowlisted to be approvable end-to-end.
Add it to the `ALLOW` list near the top of `test_approve_allowlisted_chains.py`:

```python
ALLOW = [
    "cd *",
    "echo *",
    "grep *",
    "ls *",
    "sort *",
    "find *",
    "git log *",
    "git rev-parse *",
    "git fetch *",
    "git remote -v",
    "read *",
    "uv run pytest*",
    "npm run build:*",
    "base64 *",
    "gh api repos/*/contents/*",
    "python3 -c \"import yaml; yaml.safe_load(open('*'))\"",
]
```

- [ ] **Step 2: Add failing tests**

```python
def test_inspect_approves_while_loop_body():
    segments, top_level_count, had_compound, reason = aac._inspect(
        "while read -r line; do echo $line; done"
    )
    assert reason is None
    assert segments == ["read -r line", "echo $line"]
    assert top_level_count == 1
    assert had_compound is True


def test_inspect_approves_while_loop_with_safe_input_redirect():
    segments, _, _, reason = aac._inspect(
        "while read -r line; do echo $line; done < /tmp/safe/input.txt", REDIRECT_SAFE_DIRS
    )
    assert reason is None
    assert segments == ["read -r line", "echo $line"]


def test_inspect_refuses_while_loop_with_relative_input_redirect():
    assert (
        aac._inspect("while read -r line; do echo $line; done < input.txt", REDIRECT_SAFE_DIRS)[0]
        is None
    )


def test_inspect_refuses_while_loop_with_input_redirect_outside_safe_dirs():
    assert (
        aac._inspect(
            "while read -r line; do echo $line; done < /var/secret/input.txt",
            REDIRECT_SAFE_DIRS,
        )[0]
        is None
    )


def test_inspect_refuses_while_loop_with_dynamic_input_redirect():
    assert (
        aac._inspect(
            'while read -r line; do echo $line; done < "$HOME/input.txt"', REDIRECT_SAFE_DIRS
        )[0]
        is None
    )


def test_decide_approves_while_loop_with_safe_redirect_when_body_allowlisted():
    cmd = "while read -r line; do echo $line; done < /tmp/safe/input.txt"
    assert aac.decide(cmd, ALLOW, DENY, REDIRECT_SAFE_DIRS)


def test_decide_rejects_while_loop_redirect_outside_safe_dirs_even_when_body_allowlisted():
    cmd = "while read -r line; do echo $line; done < /var/secret/input.txt"
    assert not aac.decide(cmd, ALLOW, DENY, REDIRECT_SAFE_DIRS)
```

- [ ] **Step 3: Run to verify these fail**

Run: `pytest test_approve_allowlisted_chains.py -q`
Expected: FAIL on all new `while` tests (still refused as "unsupported compound shape
(while)"); the redirect-specific ones would additionally still hit the old "refuse every
input redirect" behavior once `while` support alone is added but before Step 5 below.

- [ ] **Step 4: Enable `"while"` in the supported-keywords set**

```python
_SUPPORTED_COMPOUND_KEYWORDS: frozenset[str] = frozenset({"for", "if", "while"})
```

- [ ] **Step 5: Extend `visitredirect` with the input-redirect carve-out**

Replace the existing method body:

```python
        def visitredirect(self, n, input, type, output, heredoc) -> None:
            if isinstance(output, int):
                return  # fd duplication such as 2>&1
            word = getattr(output, "word", None)
            if word == "/dev/null":
                return
            literal_abs = word is not None and not output.parts and os.path.isabs(word)
            if (
                type in (">", ">>")
                and literal_abs
                and os.path.splitext(word)[1].lower() in _SAFE_REDIRECT_EXTENSIONS
                and _under_safe_dir(word, self._safe_dirs)
            ):
                return
            if type == "<" and literal_abs and _under_safe_dir(word, self._safe_dirs):
                return
            self._refuse(
                "redirect to a file (only fd dups, /dev/null, >/>> to a literal absolute "
                ".log/.out/.err/.tmp path under a trusted directory, and < from a literal "
                "absolute path under a trusted directory, are allowed)"
            )
```

(No extension restriction on `<`, unlike `>`/`>>`: reading a file can't clobber it, so there's
no manifest-file risk to guard against — see design doc Section 3.)

- [ ] **Step 6: Run the full suite and confirm everything passes**

Run: `pytest test_approve_allowlisted_chains.py -q`
Expected: all tests pass.

---

### Task 5: Cross-construct nesting regression test, `_selftest()` additions, and docs

**Files:**
- Modify: `test_approve_allowlisted_chains.py` (one more integration test)
- Modify: `approve-allowlisted-chains.py` (`_selftest()` fixture + cases; module docstring)
- Modify: `README.md` (rewrite "Proposed extension" section; update "Extending" table and
  "Known limitations")

**Interfaces:** none — this task only adds tests/docs, no new production code paths.

- [ ] **Step 1: Add a cross-construct nesting regression test**

This confirms the depth cap generalizes across different construct types stacked together,
not just repeated subshells (which Task 1 already covers):

```python
def test_inspect_refuses_two_levels_of_nesting_across_different_construct_types():
    # for(depth 1) > if(depth 2) > subshell(depth 3) -- one level too many.
    assert aac._inspect("for x in a; do if true; then (echo hi); fi; done")[0] is None
```

Run: `pytest test_approve_allowlisted_chains.py -q -k nesting_across`
Expected: passes immediately (no new production code needed — this is a regression check on
existing behavior from Tasks 1-4).

- [ ] **Step 2: Extend `_selftest()`'s fixture and cases**

In `approve-allowlisted-chains.py`'s `_selftest()` function, add `"read *"` to its local
`allow` list (mirrors Step 1 of Task 4, but this is a separate, hand-maintained fixture used
only by `--selftest`):

```python
    allow = [
        "cd *",
        "echo *",
        "grep *",
        "ls *",
        "sort *",
        "find *",
        "git log *",
        "git rev-parse *",
        "git fetch *",
        "git remote -v",
        "read *",
        "base64 *",
        "gh api repos/*/contents/*",
        "python3 -c \"import yaml; yaml.safe_load(open('*'))\"",
    ]
```

Then add these cases to the `cases` list (right before the closing `]`):

```python
        # compound-command support
        ("for r in dev stage prod; do git log --oneline -1 origin/$r; done", True),
        ("for r in dev stage prod; do git status --short; done", False),
        ("if git log -1; then echo clean; else echo dirty; fi", True),
        ("if git log -1; then echo clean; else git status --short; fi", False),
        ("(cd ~/dev/x && git log --oneline -1)", True),
        ("(cd ~/dev/x && git status --short)", False),
        ("while read -r line; do echo $line; done < /tmp/safe/input.txt", True),
        ("while read -r line; do echo $line; done < input.txt", False),
        ("for x in a; do if true; then (echo hi); fi; done", False),  # nested 3 deep
        ('case "$x" in a) echo a;; esac', False),  # case stays unparseable/unsupported
```

- [ ] **Step 3: Run the selftest and confirm it passes**

Run: `python3 approve-allowlisted-chains.py --selftest`
Expected: `N/N passed` with `N` now 10 higher than the count recorded at the end of Task 1.

- [ ] **Step 4: Rewrite the README's "Proposed extension" section**

In `README.md`, replace the entire `## Proposed extension: compound commands (not yet
implemented)` section (including its three subsections) with:

```markdown
## Compound command support

`for`, `if`/`elif`/`else`, `while`, and subshell/group (`(...)`/`{...}`) commands are
inspected rather than refused outright: every command that could possibly execute — across
every loop iteration and every branch — must match an allow rule, exactly like a plain
chain's segments. A standalone compound (no `&&`/`;` chaining it to anything else) is
eligible for approval on its own, since Claude Code's native matcher never handles these
shapes at all.

- **`for var in w1 w2 ...; do body; done`** — the iteration source must be either literal
  words, or a single command substitution (`$(cmd)`/backticks) whose inner command is
  checked like any other substitution elsewhere in this hook. No separate "is this bounded"
  heuristic: if a user's own allow rules make both a broad enumerator and a broad reader
  approvable, a substitution-sourced loop combining them becomes approvable too — that's
  judged to be the user's own allow-rule risk, not a new capability this hook grants.
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
- **Functions, heredocs, inline `VAR=val` assignments** — refused anywhere, including inside
  a compound body, same as at the top level.

See `docs/2026-07-21-compound-commands-design.md` for the full design rationale.
```

- [ ] **Step 5: Update the "Extending" table**

In the same file's `## Extending` table, add rows for the new pieces (insert after the
`_ChainInspector` row):

```markdown
| `_MAX_COMPOUND_DEPTH` | Nesting cap for compound commands (1 = top-level only, 2 = one nested level allowed). |
| `_SUPPORTED_COMPOUND_KEYWORDS` | Which compound keywords (`for`/`if`/`while`) this hook walks into; subshell/group are handled unconditionally alongside it. Extend *carefully* -- adding a keyword here means its body/conditions get the same allow/deny check as a plain chain, with no further safety net. |
```

And extend the existing `_ChainInspector` row's description to mention `visitfor` and
`visitnodeend` alongside `visitredirect`.

- [ ] **Step 6: Update "Known limitations"**

Add these two bullets to the `## Known limitations` section:

```markdown
- **`case` statements are always refused** — not a design choice, a vendored-dependency
  limit (see "Compound command support" above). No configuration changes this.
- **Compound nesting deeper than one extra level always refuses**, regardless of whether
  every command inside would otherwise be allowlisted.
```

- [ ] **Step 7: Update the module docstring's safety-model bullets in `approve-allowlisted-chains.py`**

In the top-of-file docstring (the `* Command/process substitution ...` bullet list), add one
new bullet right after the compound-command sentence in the second paragraph (currently reads
"...A compound command (subshell, group, for/while/if/case), a function, an inline `VAR=val`
assignment, or a heredoc is refused outright."). Change that sentence to:

```
  `for`/`if`/`while` and subshell/group compounds are inspected (see "Compound command
  support" in README.md) rather than refused outright; `case` remains unparseable by the
  vendored bashlex, and a function, an inline `VAR=val` assignment, or a heredoc is still
  refused outright anywhere, including inside a compound body.
```

- [ ] **Step 8: Final full verification**

Run, in order, and confirm all pass:

```bash
python3 approve-allowlisted-chains.py --selftest
pytest test_approve_allowlisted_chains.py -q
python3 test_approve_allowlisted_chains.py
```

Expected: all three report full pass (no failures) with no changes needed.
