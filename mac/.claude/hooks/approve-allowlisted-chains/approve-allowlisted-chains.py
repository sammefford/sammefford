#!/usr/bin/env python3
"""Auto-approve chained Bash commands whose every segment is individually allowlisted.

Claude Code's native permission check already decomposes simple command chains and
auto-approves them when each piece matches an allow rule, but it bails to a prompt on
some shapes (observed: mixing `&&` and `;` across many segments). This PreToolUse hook
fills that gap: it parses the command with bashlex (bash's own grammar), and returns an
`allow` decision only when the command is a plain chain of >= 2 simple commands, every
segment matches an allow rule, and none matches a deny rule.

It also closes a narrower, separate gap: a command name given as an absolute path into a
known system/package-manager bin directory (e.g. `/usr/bin/tail`) is a different literal
string than the allowlisted bare form (`tail`), so CC's own prefix matching treats them as
unrelated and prompts again. This hook canonicalizes just the leading command word of each
segment — never its arguments — back to its bare form before matching, so it only needs to
be allowlisted once. This also lets a single (non-chain) command through when, and only
when, canonicalizing its absolute path is the reason it now matches — an ordinary bare
single command is still left to Claude Code's native matching, unchanged from before.

Safety model — the only dangerous divergence from Claude Code is *over*-approval, so the
design makes that impossible rather than trying to replicate CC exactly:

* Splitting and danger-detection use bashlex, not hand-rolled string scanning, so we
  agree with the shell that actually runs the command. `for`/`if`/`while` and subshell/group
  compounds are inspected (see "Compound command support" in README.md) rather than refused
  outright; `case` remains unparseable by the vendored bashlex, and a function or a heredoc
  is still refused outright anywhere, including inside a compound body. An inline `VAR=val`
  assignment is refused unless `val` is wholly a single command/process substitution
  (`VAR=$(cmd)`) with no literal text mixed in — see "Variable assignment support" in
  README.md for what that lets through and the risk it knowingly reopens.
* A redirect is allowed only as an fd dup (`2>&1`), `/dev/null`, an
  output redirect (`>`/`>>`) to a literal (no `$VAR`/`$(...)`) absolute path that both ends
  in a safe extension (`.log`, `.out`, `.err`, `.tmp`, `.diff`, `.json`) and falls under a
  trusted directory (see `_load_safe_redirect_dirs`), or an input redirect (`<`) to a
  literal absolute path under a trusted directory — no extension restriction for reads,
  since reading a file can't clobber it the way writing can. Anything else (relative
  paths, dynamic paths, an output redirect with an unsafe extension or outside a trusted
  directory) is refused outright.
* Command/process substitution (`$(...)`, backticks, `<(...)`) is not refused outright —
  its inner command is recursed into and treated as just another segment, subject to the
  same allow/deny check and the same unsafe-construct detection. This is safe because
  substitution output can only ever become argument *text* in the outer command; it is
  never re-parsed as shell syntax, so it can't smuggle in a new command. Only *top-level*
  segments count toward the "chain of >=2" gate below, so a single bare command that
  merely contains a substitution (e.g. `cat "$(git rev-parse --show-toplevel)/x"`) still
  does not qualify as a chain — it's left to Claude Code's native single-command matching.
* Allow matching uses the same `*`-anywhere glob semantics as Claude Code's own
  `Bash(...)` rules (mid-string and repeated wildcards included, e.g.
  `Bash(gh api repos/*/contents/*)`), so a chain segment is approved only when it matches
  a rule a human already wrote — never something CC's own matching wouldn't also accept.
  Rule text is also dequoted the same way bashlex dequotes a parsed command word, so a
  rule written with literal quotes (e.g. `Bash(python3 -c "import yaml; ...")`) still
  lines up with the dequoted segment text it's compared against.
* Deny matching uses the same glob semantics so it never misses a deny — and, as a
  backstop, Claude Code re-applies its own deny rules after this hook regardless, so a
  denied command is blocked even if this hook were wrong.
* Path canonicalization only strips a directory prefix that is an exact match against a
  small fixed set of known bin directories (`_KNOWN_BIN_DIRS`), and only from the first
  word of a segment (the command name). It can never alter argument text, so it can't be
  used to disguise a different command or manufacture a false wildcard match. Both the raw
  and canonicalized forms of every segment are checked against *both* allow and deny rules,
  so canonicalizing can only ever add an extra chance to match a deny rule too — never a
  way to dodge one.

On any parse failure, unsafe construct, or unexpected input it prints nothing and exits
0, so Claude Code's normal prompting takes over. It never emits `deny`.

    approve-allowlisted-chains.py --selftest      # exercise the decision logic
    approve-allowlisted-chains.py --check < cmd   # explain the verdict for one command

See README.md for the full design, safety model, wiring, and how to extend this hook.
The unit suite is test_approve_allowlisted_chains.py.
"""
from __future__ import annotations

import json
import os
import re
import sys

_VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

try:
    import bashlex
    import bashlex.ast
    import bashlex.errors
    import bashlex.shutils
except Exception:  # vendored dep missing/broken -> hook safely does nothing
    bashlex = None


def _dequote_pattern(pattern: str) -> str:
    """Strip quote characters from a `Bash(...)` rule's inner pattern the same way bashlex
    dequotes a parsed command word (see `visitcommand`), so a rule that was written with
    literal quotes -- typically because Claude Code's own native matcher needs them to
    match the raw command text, e.g. `Bash(python3 -c "import yaml; ...")` -- still lines
    up with the dequoted segment text this hook compares it against. A no-op on a pattern
    that has no quote characters."""
    if bashlex is None:
        return pattern
    try:
        return bashlex.shutils.removequotes(pattern)
    except Exception:
        return pattern


def _bash_patterns(rules: list[str]) -> list[str]:
    """Inner patterns of `Bash(...)` rules; a bare `Bash` rule becomes `*` (match all).
    Quote characters are left as-is here -- `_allow_matches`/`_deny_matches` dequote at
    match time (via `_dequote_pattern`) so it applies uniformly no matter how a caller
    obtained the pattern list, not just when routed through this function."""
    patterns: list[str] = []
    for rule in rules:
        if rule == "Bash":
            patterns.append("*")
            continue
        match = re.fullmatch(r"Bash\((.*)\)", rule)
        if match:
            patterns.append(match.group(1))
    return patterns


def _load_rules() -> tuple[list[str], list[str]]:
    """Collect allow/deny Bash patterns from the settings files Claude Code reads.

    User-level `~/.claude/settings.local.json` is intentionally skipped: it is uncertain
    whether CC applies it to permissions, and omitting a source can only make this hook
    more conservative (fewer allows), never less safe."""
    allow: list[str] = []
    deny: list[str] = []
    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    for path in (
        os.path.expanduser("~/.claude/settings.json"),
        os.path.join(project, ".claude", "settings.json"),
        os.path.join(project, ".claude", "settings.local.json"),
    ):
        try:
            with open(path, encoding="utf-8") as handle:
                perms = json.load(handle).get("permissions", {})
        except (OSError, ValueError):
            continue
        allow += perms.get("allow", [])
        deny += perms.get("deny", [])
    return _bash_patterns(allow), _bash_patterns(deny)


# Extensions with no known critical-config use, so overwriting a matching file is at
# worst clobbering a regenerable build/run artifact. Deliberately excludes `.txt`:
# requirements.txt and CMakeLists.txt are load-bearing manifests with that extension.
_SAFE_REDIRECT_EXTENSIONS = {".log", ".out", ".err", ".tmp", ".diff", ".json"}


def _load_safe_redirect_dirs() -> list[str]:
    """Absolute directory prefixes a real-file redirect may target.

    Reuses directories the user has *already* told Claude Code to trust broadly (the
    current project dir plus every `permissions.additionalDirectories` entry from the
    settings files below), plus the OS scratch dirs. Widening this list only widens which
    redirects skip a prompt — it never grants a *new* capability, since Claude Code (via
    Edit/Write) can already touch these paths freely."""
    dirs: list[str] = ["/tmp", "/private/tmp"]
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        dirs.append(tmpdir)
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project:
        dirs.append(project)
    for path in (
        os.path.expanduser("~/.claude/settings.json"),
        os.path.join(project or ".", ".claude", "settings.json"),
        os.path.join(project or ".", ".claude", "settings.local.json"),
    ):
        try:
            with open(path, encoding="utf-8") as handle:
                perms = json.load(handle).get("permissions", {})
        except (OSError, ValueError):
            continue
        dirs += perms.get("additionalDirectories", [])
    return [os.path.expanduser(d) for d in dirs]


def _under_safe_dir(path: str, safe_dirs: list[str]) -> bool:
    """True iff `path` resolves under one of `safe_dirs`. Both sides are resolved with
    `realpath` here (not by callers) so symlinked prefixes (e.g. macOS `/tmp` ->
    `/private/tmp`) can't cause a false mismatch either way."""
    resolved = os.path.realpath(path)
    for d in safe_dirs:
        resolved_dir = os.path.realpath(os.path.expanduser(d))
        if resolved == resolved_dir or resolved.startswith(resolved_dir + os.sep):
            return True
    return False


# Standard directories where system and package-manager binaries live. A command name
# resolving under one of these (and only these) is canonicalized to its bare form for
# allow/deny matching, so `Bash(tail *)` also covers `/usr/bin/tail`, `/bin/tail`, etc.
# without a separate rule per absolute path.
_KNOWN_BIN_DIRS = frozenset(
    {
        "/bin",
        "/sbin",
        "/usr/bin",
        "/usr/sbin",
        "/usr/local/bin",
        "/usr/local/sbin",
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
    }
)

# Nesting cap for compound commands: 1 = the top-level compound itself, 2 = one further
# nested compound inside its body. Anything deeper refuses outright -- see design doc.
_MAX_COMPOUND_DEPTH = 2

# Compound-command keywords this hook is willing to walk into (see design doc). Empty until
# later tasks in this plan add "for"/"if"/"while" one at a time. Subshell/group (a bare "("
# or "{" as the compound's first element) are supported unconditionally below, not gated by
# this set, since they carry no keyword node of their own.
_SUPPORTED_COMPOUND_KEYWORDS: frozenset[str] = frozenset({"for", "if", "while"})


def _is_single_substitution(value_word: str, parts) -> bool:
    """True iff `parts` (a word/assignment node's nested expansions) is exactly one
    command or process substitution, and `value_word` (the text expected to be wholly
    that substitution -- a for-loop's iteration word, or an assignment's value half
    after `NAME=`) itself starts and ends with that substitution's own delimiters.
    Checking the delimiters on `value_word` directly (rather than comparing it to the
    substitution node's own `.word`) is what catches literal text mixed in before or
    after the substitution (`prefix$(cmd)`, `$(cmd)suffix`) -- such a mix would smuggle
    un-vetted literal text in alongside the one command this hook does check, so it must
    still refuse. Shared by `visitfor` and `visitassignment`."""
    if len(parts) != 1 or parts[0].kind not in ("commandsubstitution", "processsubstitution"):
        return False
    return (
        (value_word.startswith("$(") and value_word.endswith(")"))
        or (value_word.startswith("`") and value_word.endswith("`"))
        or (value_word.startswith("<(") and value_word.endswith(")"))
    )


def _canonicalize_command_word(word: str) -> str:
    """`/usr/bin/tail` -> `tail`. Anything not under a `_KNOWN_BIN_DIRS` entry, including
    an unrecognized absolute path, is returned unchanged."""
    if os.path.dirname(word) in _KNOWN_BIN_DIRS:
        return os.path.basename(word)
    return word


def _canonicalize_segment(segment: str) -> str:
    """Canonicalize only the leading command word of a segment; everything after the
    first space (the arguments) is passed through untouched."""
    head, sep, rest = segment.partition(" ")
    return _canonicalize_command_word(head) + sep + rest


def _pattern_regex(pattern: str) -> str:
    """Build a fullmatch-anchored regex from an allow/deny pattern: every `*` becomes
    `.*`, including mid-string and repeated occurrences, matching Claude Code's own
    `Bash(...)` glob semantics (settings already rely on this, e.g.
    `Bash(gh api repos/*/contents/*)`). A trailing ` *` or `:*` is additionally treated as
    an optional suffix, so a rule like `git log *` (or `npm run build:*`) also matches the
    bare command/word with nothing after the separator at all."""
    trailing = pattern.endswith(" *") or pattern.endswith(":*")
    sep = pattern[-2] if trailing else ""
    core = pattern[:-2] if trailing else pattern
    regex = "".join(".*" if part == "*" else re.escape(part) for part in re.split(r"(\*)", core))
    if trailing:
        regex += f"(?:{re.escape(sep)}.*)?"
    return regex


def _allow_matches(segment: str, pattern: str) -> bool:
    """Glob match against an allow rule using the same `*`-anywhere semantics Claude
    Code's own `Bash(...)` rules use (see `_pattern_regex`) -- so this hook can approve any
    chain segment CC's native matcher would already accept on its own. This is a wider
    match than earlier versions of this hook (which only handled a single trailing
    wildcard); it's still bounded by the same rules a human already wrote into settings, so
    it can't approve anything CC's own matching wouldn't. `pattern` is dequoted here (not
    by the caller) so this applies uniformly regardless of whether it came through
    `_bash_patterns` or was supplied directly (e.g. in tests)."""
    pattern = _dequote_pattern(pattern)
    if "*" not in pattern:
        return segment == pattern
    return re.fullmatch(_pattern_regex(pattern), segment) is not None


def _deny_matches(segment: str, pattern: str) -> bool:
    """Deny matching: the same glob semantics as `_allow_matches` (kept as a separate
    function in case allow/deny semantics ever need to diverge again). Erring toward
    matching means we never miss a deny; a false match only costs a prompt."""
    pattern = _dequote_pattern(pattern)
    if pattern == "*":
        return True
    return re.fullmatch(_pattern_regex(pattern), segment) is not None


if bashlex is not None:

    class _ChainInspector(bashlex.ast.nodevisitor):
        """Walks a bashlex AST, collecting simple-command texts and refusing (recording a
        reason) on any construct that makes blanket approval unsafe.

        `commands` holds every simple-command segment found, including ones nested inside
        a command/process substitution or compound body. `top_level_commands` counts only the ones found
        outside any substitution or compound, so the ">=2 segment" chain gate in `decide()` can't be
        satisfied by a single command that merely contains a substitution, and a compound
        counts as one top-level item regardless of how many commands it contains.

        `safe_dirs` bounds which absolute paths a real-file redirect may target (see
        `visitredirect`); pass `[]` to refuse every real-file redirect as before."""

        def __init__(self, safe_dirs: list[str] | None = None) -> None:
            self.commands: list[str] = []
            self.top_level_commands = 0
            self.had_compound = False
            self._subst_depth = 0
            self._compound_depth = 0
            self._safe_dirs = safe_dirs or []
            self.reason: str | None = None

        def _refuse(self, why: str) -> None:
            if self.reason is None:
                self.reason = why

        def visitcommandsubstitution(self, n, command) -> bool:
            self._subst_depth += 1
            self.visit(command)
            self._subst_depth -= 1
            return False  # already recursed manually; block the base class's auto-recursion

        def visitprocesssubstitution(self, n, command) -> bool:
            self._subst_depth += 1
            self.visit(command)
            self._subst_depth -= 1
            return False

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
            single_subst = len(items) == 1 and _is_single_substitution(
                items[0].word, items[0].parts
            )
            if not (all_literal or single_subst):
                self._refuse(
                    "for loop iteration source must be a literal word list or a single "
                    "command substitution"
                )
                return False
            return None

        def visitnodeend(self, n) -> None:
            if n.kind == "compound":
                self._compound_depth -= 1

        def visitfunction(self, n, name, body, parts) -> bool:
            self._refuse("function definition")
            return False

        def visitassignment(self, n, word) -> bool | None:
            """`VAR=value`. Refused outright unless `value` is wholly a single command
            or process substitution (`VAR=$(cmd)`, `` VAR=`cmd` ``, `VAR=<(cmd)`) --
            the same single-substitution gate `visitfor` uses for a for-loop's
            iteration source (see `_is_single_substitution`). A plain literal value, or
            one mixing literal text with a substitution (`VAR=prefix$(cmd)`), still
            refuses outright: only the inner command is ever checked against
            allow/deny, so literal text folded into the same value would never be
            vetted at all, and a plain literal has no nested command to vet in the
            first place.

            When accepted, the substitution is left to the base class's own recursion
            (the same path a command word's nested substitution already takes) and this
            assignment counts as a top-level segment in its own right -- mirroring
            `visitcommand`'s own gating -- so `VAR=$(cmd) && echo "$VAR"` can qualify as
            a chain outside a loop too, not just inside one.

            Accepting this reopens a real gap the chain-of-approved-commands model
            doesn't otherwise have: the captured value can flow into a *later*,
            unrelated statement (e.g. an unquoted `echo $VAR` reinterpolating it as new
            words, or a decoded secret handed to `echo`) that this hook has no way to
            tie back to "was produced by an approved command." That risk was discussed
            and accepted deliberately (see docs/) rather than overlooked."""
            if self.reason is not None:
                return False
            value = word.partition("=")[2]
            if not _is_single_substitution(value, n.parts):
                self._refuse(
                    "inline assignment whose value is not wholly a single command "
                    "substitution (VAR=val or VAR=partial$(cmd)text)"
                )
                return False
            if self._subst_depth == 0 and self._compound_depth == 0:
                self.top_level_commands += 1
            return None  # let the base class recurse into the substitution

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
                ".log/.out/.err/.tmp/.diff/.json path under a trusted directory, and < from a literal "
                "absolute path under a trusted directory, are allowed)"
            )

        def visitcommand(self, n, parts) -> None:
            words = [p.word for p in parts if p.kind == "word"]
            if words:
                self.commands.append(" ".join(words))
                if self._subst_depth == 0 and self._compound_depth == 0:
                    self.top_level_commands += 1


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


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    allow, deny = _load_rules()
    if not command or not decide(command, allow, deny):
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "every chained segment matches an allow rule",
                }
            }
        )
    )
    return 0


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


def _selftest() -> int:
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
    deny = ["find * -exec *", "find * -delete *"]
    safe_dirs = ["/tmp/safe"]
    cases: list[tuple[str, bool]] = [
        # the exact chain that prompted, plus the two original shapes
        (
            'cd ~/dev/smefford_ao && git rev-parse --abbrev-ref HEAD 2>&1; echo "---"; '
            'git rev-parse --short HEAD 2>&1; echo "---"; git log --oneline -1 2>&1',
            True,
        ),
        (
            'cd ~/dev/x && git rev-parse --symbolic-full-name @{u} 2>&1; echo "---"; '
            'git fetch origin br 2>&1; echo "---"; git log --oneline a..b 2>&1',
            True,
        ),
        (
            'git remote -v && echo "---" && git log --oneline -5 origin/feat/x 2>&1 && '
            "echo head && git log --oneline -5 HEAD",
            True,
        ),
        ("echo abc | grep a && echo done", True),  # pipe chain, all allowlisted
        ("ls -la && find . -maxdepth 2 -type d | sort", True),  # read-only find + sort
        ("git rev-parse @{u} 2>&1 && echo done", True),  # bashlex must accept @{u}
        ("git log origin/main..HEAD --oneline && echo ok", True),  # and .. ranges
        ("git log --oneline -1", False),  # single command, not a chain
        ("/usr/bin/sort -u", True),  # lone command, but absolute path canonicalizes to an allow rule
        ("/opt/evil/sort -u", False),  # absolute path, but not under a known bin dir -> no canonicalization
        ("/usr/bin/rm -rf ~", False),  # canonicalizes to "rm", which isn't allowlisted
        ("echo hi | /usr/bin/sort -u", True),  # chain mixing a bare and an absolute-path segment
        ("echo hi && /bin/find . -delete", False),  # canonical form must still hit the deny rule
        ("echo hi && rm -rf ~", False),  # rm not allowlisted
        ("echo $(whoami) && echo hi", False),  # command substitution, but whoami isn't allowlisted
        ("echo `whoami` && echo hi", False),  # same, via backticks
        (
            'echo "$(git rev-parse --show-toplevel)" && echo hi',
            True,
        ),  # command substitution whose inner command is also allowlisted
        (
            'echo "$(git rev-parse --show-toplevel)"',
            False,
        ),  # single top-level command; a nested substitution doesn't make it a chain
        (
            'echo "$(cd x && (echo hi))" && echo bye',
            False,
        ),  # unsafe construct nested inside a substitution is still refused
        ("echo hi && git log --oneline > out.txt", False),  # file redirect
        ("echo hi && echo done > /tmp/safe/out.log", True),  # safe extension + safe dir
        ("echo hi && echo done >> /tmp/safe/out.log", True),  # append form too
        ("echo hi && echo done 2> /tmp/safe/out.err", True),  # stderr capture
        ("echo hi && echo done > /tmp/safe/out.txt", False),  # .txt deliberately excluded
        ("echo hi && echo done > /var/log/out.log", False),  # safe extension, unsafe dir
        ("echo hi && echo done > out.log", False),  # relative path always refused
        ("echo hi && echo done > /tmp/safe/$USER.log", False),  # dynamic path refused
        ("cd x && (echo hi)", True),  # subshell grouping - now approvable
        ("for d in a b; do echo $d; done", True),  # for loop with literal word list - now approvable
        ("FOO=bar git log --oneline && echo hi", False),  # env-prefixed command, not a bare assignment
        ("x=bar && echo hi", False),  # literal assignment value, no nested command to vet
        (
            "r=$(git log --oneline -1) && echo hi",
            True,
        ),  # VAR=$(cmd): assignment approvable when the nested command is allowlisted
        (
            "r=$(git status) && echo hi",
            False,
        ),  # VAR=$(cmd) but git status isn't allowlisted
        (
            "r=a$(git log -1) && echo hi",
            False,
        ),  # literal text mixed into the substitution -- still refused
        (
            "for b in x y; do r=$(git log --oneline -1 origin/$b); echo \"$b -> $r\"; done",
            True,
        ),  # the exact shape that prompted this change: capture-then-echo inside a for loop
        (
            'for b in x; do r=$(git status); echo "$r"; done',
            False,
        ),  # same shape, nested command not allowlisted
        ("echo hi && find . -exec rm {} +", False),  # -exec matches deny
        ("echo hi && find . -maxdepth 1 -delete", False),  # -delete matches deny
        ("git status && echo done", False),  # git status not allowlisted
        (
            'gh api "repos/Adobe-Experience-Platform/ao-deploy/contents/k8s/helm/Stage/'
            "va7/values.yaml?ref=0f6a6015c\" --jq '.content' | base64 -d | grep 'tag:'",
            True,
        ),  # mid-string wildcard rule ("gh api repos/*/contents/*") + a quoted argument
        (
            "gh api \"repos/other-org/other-repo/statuses/abc\" | grep 'state'",
            False,
        ),  # same shape, but doesn't match the "contents" segment of the allow rule
        (
            """python3 -c "import yaml; yaml.safe_load(open('foo.yaml'))" && echo ok""",
            True,
        ),  # allow rule itself contains literal quotes around its wildcard
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
    ]
    failures = 0
    for command, expected in cases:
        actual = decide(command, allow, deny, safe_dirs)
        if actual != expected:
            failures += 1
        print(f"{'ok  ' if actual == expected else 'FAIL'} expected={expected!s:5} got={actual!s:5} :: {command[:66]}")
    print(f"\n{len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(_selftest())
    if "--check" in sys.argv[1:]:
        sys.exit(_check())
    sys.exit(main())
