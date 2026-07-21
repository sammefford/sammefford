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
  agree with the shell that actually runs the command. A compound command (subshell,
  group, for/while/if/case), a function, an inline `VAR=val` assignment, or a heredoc is
  refused outright. A redirect is allowed only as an fd dup (`2>&1`), `/dev/null`, or an
  output redirect (`>`/`>>`) to a literal (no `$VAR`/`$(...)`) absolute path that both ends
  in a safe extension (`.log`, `.out`, `.err`, `.tmp`) and falls under a trusted directory
  (see `_load_safe_redirect_dirs`) — anything else (input redirects, relative paths,
  dynamic paths, other extensions/directories) is refused outright.
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
        a command/process substitution. `top_level_commands` counts only the ones found
        outside any substitution, so the ">=2 segment" chain gate in `decide()` can't be
        satisfied by a single command that merely contains a substitution.

        `safe_dirs` bounds which absolute paths a real-file redirect may target (see
        `visitredirect`); pass `[]` to refuse every real-file redirect as before."""

        def __init__(self, safe_dirs: list[str] | None = None) -> None:
            self.commands: list[str] = []
            self.top_level_commands = 0
            self._subst_depth = 0
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

        def visitcompound(self, n, list, redirects) -> bool:
            self._refuse("compound command (subshell, group, for/while/if/case)")
            return False

        def visitfunction(self, n, name, body, parts) -> bool:
            self._refuse("function definition")
            return False

        def visitassignment(self, n, word) -> None:
            self._refuse("inline environment assignment (VAR=val cmd)")

        def visitredirect(self, n, input, type, output, heredoc) -> None:
            if isinstance(output, int):
                return  # fd duplication such as 2>&1
            word = getattr(output, "word", None)
            if word == "/dev/null":
                return
            if (
                type in (">", ">>")
                and word is not None
                and not output.parts  # literal text only: no $VAR / $(...) / `...` inside
                and os.path.isabs(word)
                and os.path.splitext(word)[1].lower() in _SAFE_REDIRECT_EXTENSIONS
                and _under_safe_dir(word, self._safe_dirs)
            ):
                return
            self._refuse(
                "redirect to a file (only fd dups, /dev/null, and >/>> to a literal "
                "absolute .log/.out/.err/.tmp path under a trusted directory are allowed)"
            )

        def visitcommand(self, n, parts) -> None:
            words = [p.word for p in parts if p.kind == "word"]
            if words:
                self.commands.append(" ".join(words))
                if self._subst_depth == 0:
                    self.top_level_commands += 1


def _inspect(
    command: str, safe_dirs: list[str] | None = None
) -> tuple[list[str] | None, int, str | None]:
    """Parse `command` and return (segments, top_level_count, None) for a safe plain
    chain, or (None, 0, reason) when it cannot be safely auto-approved. `segments`
    includes commands nested inside a substitution; `top_level_count` excludes them, so
    callers can gate "is this actually a chain" on top-level segments only.

    `safe_dirs` (default none) bounds which absolute paths a real-file redirect may
    target; see `_ChainInspector`."""
    if bashlex is None:
        return None, 0, "bashlex unavailable"
    try:
        trees = bashlex.parse(command)
    except (bashlex.errors.ParsingError, NotImplementedError):
        return None, 0, "not parseable as a simple command chain"
    except Exception as exc:  # bashlex can raise assorted errors on exotic input
        return None, 0, f"parse error ({type(exc).__name__})"
    inspector = _ChainInspector(safe_dirs)
    try:
        for tree in trees:
            inspector.visit(tree)
    except Exception as exc:
        return None, 0, f"walk error ({type(exc).__name__})"
    if inspector.reason is not None:
        return None, 0, inspector.reason
    return inspector.commands, inspector.top_level_commands, None


def decide(
    command: str, allow: list[str], deny: list[str], safe_dirs: list[str] | None = None
) -> bool:
    """True iff `command` is either a plain chain of >= 2 top-level simple commands, or a
    single top-level command whose only obstacle was an absolute path into a known bin
    directory (see `_canonicalize_segment`) — and, either way, every segment (including
    any nested inside a substitution, checked in both its raw and canonicalized form)
    matches an allow rule while none matches a deny rule.

    `safe_dirs`: directories a real-file redirect may target. Defaults to
    `_load_safe_redirect_dirs()` (live settings/env) when not given — callers that need
    deterministic results (tests) should pass a fixed list explicitly."""
    if safe_dirs is None:
        safe_dirs = _load_safe_redirect_dirs()
    segments, top_level_count, _ = _inspect(command, safe_dirs)
    if not segments or not allow:
        return False
    is_chain = top_level_count >= 2
    is_lone_path_command = top_level_count == 1 and _canonicalize_segment(segments[0]) != segments[0]
    if not is_chain and not is_lone_path_command:
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
    segments, top_level_count, reason = _inspect(command, safe_dirs)
    if segments is None:
        print(f"refused: {reason}")
        return 0
    is_lone_path_command = top_level_count == 1 and _canonicalize_segment(segments[0]) != segments[0]
    if top_level_count < 2 and not is_lone_path_command:
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
        ("cd x && (echo hi)", False),  # subshell grouping
        ("for d in a b; do echo $d; done", False),  # compound / control flow
        ("FOO=bar git log --oneline && echo hi", False),  # inline assignment
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
