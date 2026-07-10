#!/usr/bin/env python3
"""Auto-approve chained Bash commands whose every segment is individually allowlisted.

Claude Code's native permission check already decomposes simple command chains and
auto-approves them when each piece matches an allow rule, but it bails to a prompt on
some shapes (observed: mixing `&&` and `;` across many segments). This PreToolUse hook
fills that gap: it parses the command with bashlex (bash's own grammar), and returns an
`allow` decision only when the command is a plain chain of >= 2 simple commands, every
segment matches an allow rule, and none matches a deny rule.

Safety model — the only dangerous divergence from Claude Code is *over*-approval, so the
design makes that impossible rather than trying to replicate CC exactly:

* Splitting and danger-detection use bashlex, not hand-rolled string scanning, so we
  agree with the shell that actually runs the command. Anything with command/process
  substitution, a compound command (subshell, group, for/while/if/case), a function, an
  inline `VAR=val` assignment, a heredoc, or a redirect to anything but an fd dup
  (`2>&1`) or `/dev/null` is refused outright.
* Allow matching is a deliberately *conservative subset* of CC's rule semantics (exact
  match or a single trailing wildcard only). Under-matching just means a normal prompt;
  it can never approve something CC would not.
* Deny matching is *liberal* (full `*` wildcards) so it never misses a deny — and, as a
  backstop, Claude Code re-applies its own deny rules after this hook regardless, so a
  denied command is blocked even if this hook were wrong.

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
except Exception:  # vendored dep missing/broken -> hook safely does nothing
    bashlex = None


def _bash_patterns(rules: list[str]) -> list[str]:
    """Inner patterns of `Bash(...)` rules; a bare `Bash` rule becomes `*` (match all)."""
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


def _allow_matches(segment: str, pattern: str) -> bool:
    """Conservative subset of CC's Bash-rule semantics: exact match, or a single trailing
    wildcard (`verb *`, `verb:*`, `verb*`). Any mid-string or repeated `*` is treated as
    no-match, so those rules simply fall through to a normal prompt. Deliberately matches
    less than CC, so the hook can never approve something CC would reject."""
    if "*" not in pattern:
        return segment == pattern
    if pattern.count("*") == 1 and pattern.endswith("*"):
        base = pattern[:-1]
        if base.endswith((" ", ":")):
            return segment == base[:-1] or segment.startswith(base)
        return segment.startswith(base)
    return False


def _deny_matches(segment: str, pattern: str) -> bool:
    """Liberal match for deny rules: `*` is a wildcard anywhere, anchored to the whole
    segment (a trailing ` *` also matches the bare base). Erring toward matching means we
    never miss a deny; a false match only costs a prompt."""
    if pattern == "*":
        return True
    trailing = pattern.endswith(" *")
    core = pattern[:-2] if trailing else pattern
    regex = "".join(".*" if part == "*" else re.escape(part) for part in re.split(r"(\*)", core))
    if trailing:
        regex += r"(?: .*)?"
    return re.fullmatch(regex, segment) is not None


if bashlex is not None:

    class _ChainInspector(bashlex.ast.nodevisitor):
        """Walks a bashlex AST, collecting simple-command texts and refusing (recording a
        reason) on any construct that makes blanket approval unsafe."""

        def __init__(self) -> None:
            self.commands: list[str] = []
            self.reason: str | None = None

        def _refuse(self, why: str) -> None:
            if self.reason is None:
                self.reason = why

        def visitcommandsubstitution(self, n, command) -> bool:
            self._refuse("command substitution $(...) or backticks")
            return False

        def visitprocesssubstitution(self, n, command) -> bool:
            self._refuse("process substitution <(...) or >(...)")
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
            if getattr(output, "word", None) == "/dev/null":
                return
            self._refuse("redirect to a file (only fd dups and /dev/null allowed)")

        def visitcommand(self, n, parts) -> None:
            words = [p.word for p in parts if p.kind == "word"]
            if words:
                self.commands.append(" ".join(words))


def _inspect(command: str) -> tuple[list[str] | None, str | None]:
    """Parse `command` and return (segments, None) for a safe plain chain, or
    (None, reason) when it cannot be safely auto-approved."""
    if bashlex is None:
        return None, "bashlex unavailable"
    try:
        trees = bashlex.parse(command)
    except (bashlex.errors.ParsingError, NotImplementedError):
        return None, "not parseable as a simple command chain"
    except Exception as exc:  # bashlex can raise assorted errors on exotic input
        return None, f"parse error ({type(exc).__name__})"
    inspector = _ChainInspector()
    try:
        for tree in trees:
            inspector.visit(tree)
    except Exception as exc:
        return None, f"walk error ({type(exc).__name__})"
    if inspector.reason is not None:
        return None, inspector.reason
    return inspector.commands, None


def decide(command: str, allow: list[str], deny: list[str]) -> bool:
    """True iff `command` is a plain chain of >= 2 simple commands, each matching an
    allow rule and none matching a deny rule."""
    segments, _ = _inspect(command)
    if not segments or len(segments) < 2 or not allow:
        return False
    for segment in segments:
        if any(_deny_matches(segment, pattern) for pattern in deny):
            return False
        if not any(_allow_matches(segment, pattern) for pattern in allow):
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
    verdict = decide(command, allow, deny)
    print(f"decision: {'AUTO-APPROVE (no prompt)' if verdict else 'DEFER to normal prompt'}\n")
    segments, reason = _inspect(command)
    if segments is None:
        print(f"refused: {reason}")
        return 0
    if len(segments) < 2:
        print(f"deferred: not a chain ({len(segments)} segment)")
        return 0
    for segment in segments:
        denied = next((p for p in deny if _deny_matches(segment, p)), None)
        allowed = next((p for p in allow if _allow_matches(segment, p)), None)
        if denied:
            tag = f"DENIED by Bash({denied})"
        elif allowed:
            tag = f"ok via Bash({allowed})"
        else:
            tag = "NO MATCHING ALLOW RULE"
        mark = "ok  " if allowed and not denied else "FAIL"
        print(f"  [{mark}] {segment}   -> {tag}")
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
    ]
    deny = ["find * -exec *", "find * -delete *"]
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
        ("echo hi && rm -rf ~", False),  # rm not allowlisted
        ("echo $(whoami) && echo hi", False),  # command substitution
        ("echo `whoami` && echo hi", False),  # backticks
        ("echo hi && git log --oneline > out.txt", False),  # file redirect
        ("cd x && (echo hi)", False),  # subshell grouping
        ("for d in a b; do echo $d; done", False),  # compound / control flow
        ("FOO=bar git log --oneline && echo hi", False),  # inline assignment
        ("echo hi && find . -exec rm {} +", False),  # -exec matches deny
        ("echo hi && find . -maxdepth 1 -delete", False),  # -delete matches deny
        ("git status && echo done", False),  # git status not allowlisted
    ]
    failures = 0
    for command, expected in cases:
        actual = decide(command, allow, deny)
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
