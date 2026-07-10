#!/usr/bin/env python3
"""Unit tests for approve-allowlisted-chains.py.

Runnable two ways:
    python3 test_approve_allowlisted_chains.py     # standalone, no pytest needed
    pytest  test_approve_allowlisted_chains.py

Tests use fixed rule fixtures, never the live settings, so results are deterministic.
See approve-allowlisted-chains.README.md for the design and safety model.
"""
import importlib.util
import pathlib

# The hook filename is hyphenated (not an importable module name), so load it by path.
_HOOK = pathlib.Path(__file__).with_name("approve-allowlisted-chains.py")
_spec = importlib.util.spec_from_file_location("approve_allowlisted_chains", _HOOK)
aac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aac)

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
    "uv run pytest*",
    "npm run build:*",
]
DENY = ["find * -exec *", "find * -delete *"]


# --- dependency sanity -------------------------------------------------------
def test_bashlex_is_vendored():
    # If this fails, run: uv pip install --target ~/.claude/hooks/vendor bashlex
    assert aac.bashlex is not None


# --- _bash_patterns ----------------------------------------------------------
def test_bash_patterns_extracts_inner_and_ignores_non_bash():
    got = aac._bash_patterns(["Bash(git log *)", "Bash", "Edit(x)", "Bash(echo *)"])
    assert got == ["git log *", "*", "echo *"]


# --- _allow_matches: conservative subset -------------------------------------
def test_allow_exact_match_only():
    assert aac._allow_matches("git remote -v", "git remote -v")
    assert not aac._allow_matches("git remote -v --foo", "git remote -v")


def test_allow_trailing_space_wildcard():
    assert aac._allow_matches("git log --oneline", "git log *")
    assert aac._allow_matches("git log", "git log *")  # bare base
    assert not aac._allow_matches("git logfoo", "git log *")  # needs a boundary


def test_allow_trailing_nospace_wildcard():
    assert aac._allow_matches("uv run pytest tests/", "uv run pytest*")
    assert aac._allow_matches("uv run pytest", "uv run pytest*")


def test_allow_colon_wildcard():
    assert aac._allow_matches("npm run build", "npm run build:*")
    assert aac._allow_matches("npm run build:prod", "npm run build:*")


def test_allow_midstring_star_is_ignored():
    # Conservative: a mid-string '*' never matches, so such rules just prompt.
    assert not aac._allow_matches("gh api repos/x/statuses y", "gh api repos/*/statuses *")


def test_allow_bare_star_matches_anything():
    assert aac._allow_matches("literally anything", "*")


# --- _deny_matches: liberal ---------------------------------------------------
def test_deny_midstring_wildcard_matches():
    assert aac._deny_matches("find . -maxdepth 1 -exec rm {} +", "find * -exec *")
    assert aac._deny_matches("find . -delete", "find * -delete *")


def test_deny_no_false_positive_on_readonly_find():
    assert not aac._deny_matches("find . -maxdepth 2 -type d", "find * -exec *")


# --- _inspect: parsing, splitting, danger detection --------------------------
def test_inspect_simple_chain_splits_and_drops_redirects():
    segments, reason = aac._inspect("cd x && git log -1 2>&1; echo hi | grep h")
    assert reason is None
    assert segments == ["cd x", "git log -1", "echo hi", "grep h"]


def test_inspect_refuses_command_substitution():
    assert aac._inspect("echo $(whoami) && echo ok")[0] is None
    assert aac._inspect("echo `whoami`")[0] is None


def test_inspect_refuses_process_substitution():
    assert aac._inspect("diff <(a) <(b)")[0] is None


def test_inspect_refuses_compound_and_subshell():
    assert aac._inspect("for d in a b; do echo $d; done")[0] is None
    assert aac._inspect("(echo hi)")[0] is None


def test_inspect_refuses_inline_assignment():
    assert aac._inspect("FOO=bar echo hi")[0] is None


def test_inspect_refuses_file_redirect_but_allows_fd_and_devnull():
    assert aac._inspect("echo hi > out.txt")[0] is None
    assert aac._inspect("echo hi 2>&1")[0] == ["echo hi"]
    assert aac._inspect("cat x 2>/dev/null")[0] == ["cat x"]


def test_inspect_keeps_quoted_operators_inside_one_command():
    # The ';' and '&&' are inside quotes -> a single echo argument, not splits.
    segments, reason = aac._inspect('echo "a; rm -rf ~ && reboot"')
    assert reason is None
    assert segments == ["echo a; rm -rf ~ && reboot"]


# --- decide: end-to-end ------------------------------------------------------
def test_decide_approves_the_chain_that_prompted():
    cmd = (
        'cd ~/dev/x && git rev-parse --abbrev-ref HEAD 2>&1; echo "---"; '
        'git rev-parse --short HEAD 2>&1; echo "---"; git log --oneline -1 2>&1'
    )
    assert aac.decide(cmd, ALLOW, DENY)


def test_decide_approves_pipe_and_readonly_find():
    assert aac.decide("echo abc | grep a && echo done", ALLOW, DENY)
    assert aac.decide("ls -la && find . -maxdepth 2 -type d | sort", ALLOW, DENY)


def test_decide_rejects_single_command():
    assert not aac.decide("git log -1", ALLOW, DENY)


def test_decide_rejects_unlisted_segment():
    assert not aac.decide("echo hi && rm -rf ~", ALLOW, DENY)


def test_decide_rejects_dangerous_constructs():
    assert not aac.decide("echo $(whoami) && echo hi", ALLOW, DENY)
    assert not aac.decide("echo hi && git log > out.txt", ALLOW, DENY)
    assert not aac.decide("FOO=bar git log && echo hi", ALLOW, DENY)
    assert not aac.decide("for d in a b; do echo $d; done", ALLOW, DENY)


def test_decide_deny_beats_allow_even_when_verb_is_allowed():
    # `find *` is allowlisted, but the deny rules must still block these.
    assert not aac.decide("echo hi && find . -exec rm {} +", ALLOW, DENY)
    assert not aac.decide("echo hi && find . -maxdepth 1 -delete", ALLOW, DENY)


def test_decide_quoted_injection_is_a_harmless_single_command():
    # The ';' is quoted, so this is two echo commands -> safe to approve.
    assert aac.decide('echo "a; rm -rf ~" && echo ok', ALLOW, DENY)


def test_decide_requires_allow_rules():
    assert not aac.decide("echo a && echo b", [], DENY)


def _run_standalone() -> int:
    tests = sorted(
        (name, fn)
        for name, fn in globals().items()
        if name.startswith("test_") and callable(fn)
    )
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"ok   {name}")
        except Exception as exc:  # noqa: BLE001 - report every failure, keep going
            failed += 1
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    import sys

    sys.exit(_run_standalone())
