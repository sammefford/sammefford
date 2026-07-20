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
# Empty on purpose: none of the pre-existing tests below need a real-file redirect to
# succeed, so forcing "no directory is safe" keeps them exercising the exact same
# behavior as before the safe-redirect feature existed.
SAFE_DIRS: list[str] = []
# Used only by the safe-redirect-specific tests further down.
REDIRECT_SAFE_DIRS = ["/tmp/safe"]


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


# --- _canonicalize_command_word / _canonicalize_segment: path canonicalization ----
def test_canonicalize_command_word_strips_known_bin_dir():
    assert aac._canonicalize_command_word("/usr/bin/tail") == "tail"
    assert aac._canonicalize_command_word("/bin/cat") == "cat"
    assert aac._canonicalize_command_word("/opt/homebrew/bin/rg") == "rg"


def test_canonicalize_command_word_leaves_unknown_dir_unchanged():
    assert aac._canonicalize_command_word("/opt/evil/tail") == "/opt/evil/tail"
    assert aac._canonicalize_command_word("tail") == "tail"


def test_canonicalize_segment_only_touches_the_command_name():
    assert aac._canonicalize_segment("/usr/bin/tail -n 5 /tmp/x") == "tail -n 5 /tmp/x"
    assert aac._canonicalize_segment("/usr/bin/tail") == "tail"  # no-arg segment, no trailing space
    assert aac._canonicalize_segment("tail -n 5") == "tail -n 5"  # already bare -> unchanged


# --- _deny_matches: liberal ---------------------------------------------------
def test_deny_midstring_wildcard_matches():
    assert aac._deny_matches("find . -maxdepth 1 -exec rm {} +", "find * -exec *")
    assert aac._deny_matches("find . -delete", "find * -delete *")


def test_deny_no_false_positive_on_readonly_find():
    assert not aac._deny_matches("find . -maxdepth 2 -type d", "find * -exec *")


# --- _inspect: parsing, splitting, danger detection --------------------------
def test_inspect_simple_chain_splits_and_drops_redirects():
    segments, top_level_count, reason = aac._inspect("cd x && git log -1 2>&1; echo hi | grep h")
    assert reason is None
    assert segments == ["cd x", "git log -1", "echo hi", "grep h"]
    assert top_level_count == 4


def test_inspect_recurses_into_command_substitution():
    # The substitution's inner command becomes an extra segment, not an outright refusal.
    segments, top_level_count, reason = aac._inspect('echo "$(git rev-parse HEAD)" && echo ok')
    assert reason is None
    # bashlex strips the surrounding quotes from the extracted word text.
    assert segments == ["echo $(git rev-parse HEAD)", "git rev-parse HEAD", "echo ok"]
    assert top_level_count == 2  # the nested segment doesn't count toward the chain gate


def test_inspect_recurses_into_backticks_too():
    segments, top_level_count, reason = aac._inspect("echo `whoami`")
    assert reason is None
    assert segments == ["echo `whoami`", "whoami"]
    assert top_level_count == 1  # single top-level command; substitution doesn't make a chain


def test_inspect_still_refuses_unsafe_construct_nested_inside_substitution():
    assert aac._inspect('echo "$(cd x && (echo hi))" && echo bye')[0] is None


def test_inspect_recurses_into_process_substitution():
    segments, top_level_count, reason = aac._inspect("diff <(git log) <(git fetch)")
    assert reason is None
    assert segments == ["diff <(git log) <(git fetch)", "git log", "git fetch"]
    assert top_level_count == 1  # one top-level command; process substitution isn't a chain


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
    segments, _, reason = aac._inspect('echo "a; rm -rf ~ && reboot"')
    assert reason is None
    assert segments == ["echo a; rm -rf ~ && reboot"]


# --- _under_safe_dir -----------------------------------------------------------
def test_under_safe_dir_matches_nested_path():
    assert aac._under_safe_dir("/tmp/safe/sub/out.log", ["/tmp/safe"])
    assert aac._under_safe_dir("/tmp/safe/out.log", ["/tmp/safe"])  # dir itself, not just nested


def test_under_safe_dir_rejects_sibling_and_prefix_lookalike():
    assert not aac._under_safe_dir("/tmp/other/out.log", ["/tmp/safe"])
    # "/tmp/safe2" must not match a rule for "/tmp/safe" via naive string prefixing.
    assert not aac._under_safe_dir("/tmp/safe2/out.log", ["/tmp/safe"])


def test_under_safe_dir_resolves_symlinked_prefixes_on_both_sides():
    # On macOS /tmp -> /private/tmp; this must match regardless of which spelling is used.
    assert aac._under_safe_dir("/tmp/safe/out.log", ["/private/tmp/safe"])
    assert aac._under_safe_dir("/private/tmp/safe/out.log", ["/tmp/safe"])


# --- _inspect / visitredirect: the safe-redirect extension ------------------
def test_inspect_allows_safe_extension_under_safe_dir():
    assert aac._inspect("echo hi > /tmp/safe/out.log", REDIRECT_SAFE_DIRS)[0] == ["echo hi"]
    assert aac._inspect("echo hi >> /tmp/safe/out.log", REDIRECT_SAFE_DIRS)[0] == ["echo hi"]
    assert aac._inspect("echo hi 2> /tmp/safe/out.err", REDIRECT_SAFE_DIRS)[0] == ["echo hi"]


def test_inspect_rejects_unsafe_extension_even_under_safe_dir():
    # .txt is deliberately excluded (requirements.txt / CMakeLists.txt risk).
    assert aac._inspect("echo hi > /tmp/safe/out.txt", REDIRECT_SAFE_DIRS)[0] is None
    assert aac._inspect("echo hi > /tmp/safe/out.json", REDIRECT_SAFE_DIRS)[0] is None


def test_inspect_rejects_safe_extension_outside_safe_dir():
    assert aac._inspect("echo hi > /var/log/out.log", REDIRECT_SAFE_DIRS)[0] is None


def test_inspect_rejects_relative_redirect_path_even_with_safe_dirs_configured():
    # Resolving a relative path would require knowing the effective cwd (which a prior
    # `cd` in the chain could have changed) -> always refused, never auto-approved.
    assert aac._inspect("echo hi > out.log", REDIRECT_SAFE_DIRS)[0] is None


def test_inspect_rejects_dynamic_redirect_path():
    # A $VAR / $(...) / `...` inside the target means the literal text isn't the real
    # path, so it can't be safely checked -> refused.
    assert aac._inspect('echo hi > "$HOME/out.log"', REDIRECT_SAFE_DIRS)[0] is None
    assert aac._inspect('echo hi > "$(pwd)/out.log"', REDIRECT_SAFE_DIRS)[0] is None


def test_inspect_rejects_input_redirect_even_when_extension_and_dir_match():
    # Only `>`/`>>` (writes) are eligible; `<` (reads arbitrary file content into the
    # command) keeps the old behavior of refusing any non-fd-dup/non-/dev/null redirect.
    assert aac._inspect("cat < /tmp/safe/out.log", REDIRECT_SAFE_DIRS)[0] is None


def test_decide_approves_chain_with_safe_redirect():
    assert aac.decide("echo hi && echo done > /tmp/safe/out.log", ALLOW, DENY, REDIRECT_SAFE_DIRS)


def test_decide_rejects_chain_with_redirect_outside_safe_dirs():
    assert not aac.decide(
        "echo hi && echo done > /tmp/safe/out.log", ALLOW, DENY, SAFE_DIRS
    )  # empty safe_dirs: same command, no trusted directory configured


def test_decide_defaults_to_loading_live_safe_dirs_when_omitted():
    # No 4th arg -> decide() falls back to _load_safe_redirect_dirs() (live settings/env),
    # not to "everything refused". A relative-path redirect is refused regardless of
    # whatever the live settings say, so this stays deterministic without mocking.
    assert not aac.decide("echo hi && echo done > out.log", ALLOW, DENY)


# --- decide: end-to-end ------------------------------------------------------
def test_decide_approves_the_chain_that_prompted():
    cmd = (
        'cd ~/dev/x && git rev-parse --abbrev-ref HEAD 2>&1; echo "---"; '
        'git rev-parse --short HEAD 2>&1; echo "---"; git log --oneline -1 2>&1'
    )
    assert aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)


def test_decide_approves_pipe_and_readonly_find():
    assert aac.decide("echo abc | grep a && echo done", ALLOW, DENY, SAFE_DIRS)
    assert aac.decide("ls -la && find . -maxdepth 2 -type d | sort", ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_single_command():
    assert not aac.decide("git log -1", ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_unlisted_segment():
    assert not aac.decide("echo hi && rm -rf ~", ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_dangerous_constructs():
    assert not aac.decide("echo $(whoami) && echo hi", ALLOW, DENY, SAFE_DIRS)  # whoami isn't allowlisted
    assert not aac.decide("echo hi && git log > out.txt", ALLOW, DENY, SAFE_DIRS)
    assert not aac.decide("FOO=bar git log && echo hi", ALLOW, DENY, SAFE_DIRS)
    assert not aac.decide("for d in a b; do echo $d; done", ALLOW, DENY, SAFE_DIRS)


def test_decide_approves_command_substitution_when_inner_command_is_allowlisted():
    cmd = 'echo "$(git rev-parse --show-toplevel)/x" && echo hi'
    assert aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_substitution_whose_inner_command_isnt_allowlisted():
    assert not aac.decide('echo "$(whoami)/x" && echo hi', ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_single_command_that_merely_contains_a_substitution():
    # Only one top-level command -> not a chain, even though it nests an allowlisted one.
    assert not aac.decide('echo "$(git rev-parse --show-toplevel)/x"', ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_unsafe_construct_nested_inside_substitution():
    assert not aac.decide('echo "$(cd x && (echo hi))" && echo bye', ALLOW, DENY, SAFE_DIRS)


def test_decide_deny_beats_allow_even_when_verb_is_allowed():
    # `find *` is allowlisted, but the deny rules must still block these.
    assert not aac.decide("echo hi && find . -exec rm {} +", ALLOW, DENY, SAFE_DIRS)
    assert not aac.decide("echo hi && find . -maxdepth 1 -delete", ALLOW, DENY, SAFE_DIRS)


def test_decide_quoted_injection_is_a_harmless_single_command():
    # The ';' is quoted, so this is two echo commands -> safe to approve.
    assert aac.decide('echo "a; rm -rf ~" && echo ok', ALLOW, DENY, SAFE_DIRS)


def test_decide_requires_allow_rules():
    assert not aac.decide("echo a && echo b", [], DENY, SAFE_DIRS)


# --- decide: absolute-path canonicalization -----------------------------------
def test_decide_approves_lone_command_via_known_bin_dir():
    # Single command, not a chain -- but canonicalizing the absolute path is exactly
    # what makes this match an allow rule CC's own matcher wouldn't have hit.
    assert aac.decide("/usr/bin/sort -u", ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_lone_command_via_unknown_absolute_path():
    # Not under a known bin dir -> no canonicalization -> unchanged, still just a
    # single non-chain command -> deferred like any other single command.
    assert not aac.decide("/opt/evil/sort -u", ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_lone_command_whose_canonical_form_isnt_allowlisted():
    assert not aac.decide("/usr/bin/rm -rf ~", ALLOW, DENY, SAFE_DIRS)


def test_decide_approves_chain_mixing_bare_and_absolute_path_segments():
    assert aac.decide("echo hi | /usr/bin/sort -u", ALLOW, DENY, SAFE_DIRS)


def test_decide_canonicalized_form_still_hits_deny_rule():
    # The deny rule text ("find * -delete *") only matches the bare form; canonicalizing
    # must not let an absolute-path invocation dodge it.
    assert not aac.decide("echo hi && /bin/find . -delete", ALLOW, DENY, SAFE_DIRS)


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
