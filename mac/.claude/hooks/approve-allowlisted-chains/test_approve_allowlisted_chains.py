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
    "read *",
    "uv run pytest*",
    "npm run build:*",
    "base64 *",
    "gh api repos/*/contents/*",
    "python3 -c \"import yaml; yaml.safe_load(open('*'))\"",
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


def test_allow_midstring_and_repeated_wildcards_match():
    # Mid-string and repeated '*' now match, mirroring CC's own glob semantics -- these
    # rules already exist in real settings.json (e.g. Bash(gh api repos/*/contents/*)).
    assert aac._allow_matches("gh api repos/x/statuses y", "gh api repos/*/statuses *")
    assert aac._allow_matches(
        "gh api repos/adobe/ao-deploy/contents/k8s/values.yaml --jq .content",
        "gh api repos/*/contents/*",
    )
    # still anchored: a segment that doesn't line up with the literal parts must not match
    assert not aac._allow_matches("gh api repos/x/statuses/y", "gh api repos/*/contents/*")


def test_allow_bare_star_matches_anything():
    assert aac._allow_matches("literally anything", "*")


# --- _dequote_pattern / quoted allow rules -----------------------------------
def test_dequote_pattern_is_noop_without_quotes():
    assert aac._dequote_pattern("git log *") == "git log *"


def test_dequote_pattern_strips_quotes_like_bashlex_dequotes_a_word():
    # bashlex strips the *outer* quotes from a parsed command word (see
    # test_inspect_recurses_into_command_substitution below); a rule written with quotes
    # for CC's own native matcher needs the same treatment to line up with that word.
    pattern = """python3 -c "import yaml; yaml.safe_load(open('*'))\""""
    assert aac._dequote_pattern(pattern) == """python3 -c import yaml; yaml.safe_load(open('*'))"""


def test_allow_matches_a_rule_containing_literal_quotes():
    pattern = """python3 -c "import yaml; yaml.safe_load(open('*'))\""""
    segment = "python3 -c import yaml; yaml.safe_load(open('foo.yaml'))"  # as bashlex extracts it
    assert aac._allow_matches(segment, pattern)


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


def test_inspect_still_refuses_unsafe_construct_nested_inside_substitution():
    assert aac._inspect('echo "$(cd x && (echo hi))" && echo bye')[0] is None


def test_inspect_recurses_into_process_substitution():
    segments, top_level_count, had_compound, reason = aac._inspect(
        "diff <(git log) <(git fetch)"
    )
    assert reason is None
    assert segments == ["diff <(git log) <(git fetch)", "git log", "git fetch"]
    assert top_level_count == 1  # one top-level command; process substitution isn't a chain


def test_inspect_refuses_inline_assignment():
    # Env-var-prefixed command invocation (assignment value "bar" is a plain literal,
    # not a substitution) -- distinct from the VAR=$(cmd) exception tested below.
    assert aac._inspect("FOO=bar echo hi")[0] is None


def test_inspect_refuses_file_redirect_but_allows_fd_and_devnull():
    assert aac._inspect("echo hi > out.txt")[0] is None
    assert aac._inspect("echo hi 2>&1")[0] == ["echo hi"]
    assert aac._inspect("cat x 2>/dev/null")[0] == ["cat x"]


def test_inspect_keeps_quoted_operators_inside_one_command():
    # The ';' and '&&' are inside quotes -> a single echo argument, not splits.
    segments, _, had_compound, reason = aac._inspect('echo "a; rm -rf ~ && reboot"')
    assert reason is None
    assert segments == ["echo a; rm -rf ~ && reboot"]
    assert had_compound is False


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
    assert aac._inspect("echo hi > /tmp/safe/out.json", REDIRECT_SAFE_DIRS)[0] == ["echo hi"]
    assert aac._inspect("echo hi > /tmp/safe/out.diff", REDIRECT_SAFE_DIRS)[0] == ["echo hi"]


def test_inspect_rejects_unsafe_extension_even_under_safe_dir():
    # .txt is deliberately excluded (requirements.txt / CMakeLists.txt risk).
    assert aac._inspect("echo hi > /tmp/safe/out.txt", REDIRECT_SAFE_DIRS)[0] is None
    # .py is not in _SAFE_REDIRECT_EXTENSIONS at all -- overwriting a script is real risk.
    assert aac._inspect("echo hi > /tmp/safe/out.py", REDIRECT_SAFE_DIRS)[0] is None


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


def test_inspect_approves_input_redirect_from_safe_dir_with_literal_absolute_path():
    # Input redirects `<` from literal absolute paths under safe directories are now
    # approved (Task 4), unlike output redirects which require a safe extension.
    segments, _, _, reason = aac._inspect("cat < /tmp/safe/out.log", REDIRECT_SAFE_DIRS)
    assert reason is None
    assert segments == ["cat"]


def test_inspect_approves_input_redirect_with_no_extension_restriction():
    # Unlike output redirects (which require a safe extension -- see
    # _SAFE_REDIRECT_EXTENSIONS), an input redirect has no extension gate at all: reading
    # a file can't clobber it, so an extension that would be refused for a write (or one
    # not in the safe list, e.g. .pem/.key-shaped names) is still fine to read from,
    # provided the path is still literal, absolute, and under a safe dir. This locks in
    # the exact design point Task 4 introduced, so a future edit can't quietly re-add an
    # extension check to the `<` branch "for consistency" with the `>`/`>>` branch.
    segments, _, _, reason = aac._inspect("cat < /tmp/safe/id_rsa", REDIRECT_SAFE_DIRS)
    assert reason is None
    assert segments == ["cat"]
    # .txt is deliberately excluded from _SAFE_REDIRECT_EXTENSIONS for writes; reads
    # aren't gated by that set at all, so it must still be approved here.
    assert aac._inspect("cat < /tmp/safe/secret.txt", REDIRECT_SAFE_DIRS)[0] == ["cat"]


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


# --- decide: mid-string wildcard rules + quoted arguments (the gh api scenario) ----
def test_decide_approves_chain_with_quoted_arg_against_midstring_wildcard_rule():
    # Real-world case: a quoted `gh api "repos/.../contents/..."` path piped through
    # base64 and grep, matching the allow rule Bash(gh api repos/*/contents/*).
    cmd = (
        'gh api "repos/Adobe-Experience-Platform/ao-deploy/contents/k8s/helm/Stage/'
        "va7/values.yaml?ref=0f6a6015c\" --jq '.content' | base64 -d | grep 'tag:'"
    )
    assert aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_chain_when_midstring_wildcard_rule_doesnt_line_up():
    cmd = 'gh api "repos/other-org/other-repo/statuses/abc" | grep \'state\''
    assert not aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)


def test_decide_approves_chain_with_rule_containing_literal_quotes():
    cmd = """python3 -c "import yaml; yaml.safe_load(open('foo.yaml'))" && echo ok"""
    assert aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)



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


def test_inspect_approves_two_sibling_top_level_compounds():
    # Regression test for _compound_depth counter: both compounds must be recognized as
    # top-level, not the second one treated as nested. Uses two for-loops chained together.
    segments, top_level_count, had_compound, reason = aac._inspect(
        "for a in x; do echo $a; done && for b in y; do echo $b; done"
    )
    assert reason is None
    assert segments == ["echo $a", "echo $b"]
    assert top_level_count == 2
    assert had_compound is True


def test_decide_approves_two_sibling_top_level_compounds():
    # End-to-end approval when both for-loops' commands are allowlisted. The dedicated
    # regression guard for _compound_depth resetting between top-level items is the
    # `top_level_count == 2` assertion in test_inspect_approves_two_sibling_top_level_compounds
    # above -- decide()'s is_lone_compound branch would also accept a miscounted "1" here,
    # so this test alone wouldn't catch that regression.
    cmd = "for a in x; do echo $a; done && for b in y; do echo $b; done"
    assert aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)


# --- for-loop support -------------------------------------------------------
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


# --- if/elif/else support ---------------------------------------------------
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


def test_inspect_refuses_two_levels_of_nesting_across_different_construct_types():
    # for(depth 1) > if(depth 2) > subshell(depth 3) -- one level too many.
    assert aac._inspect("for x in a; do if true; then (echo hi); fi; done")[0] is None


# --- VAR=$(cmd) assignment support -------------------------------------------
def test_inspect_approves_assignment_whose_value_is_a_single_substitution():
    segments, top_level_count, had_compound, reason = aac._inspect(
        "r=$(git log --oneline -1) && echo hi"
    )
    assert reason is None
    assert segments == ["git log --oneline -1", "echo hi"]
    # the assignment counts as a top-level segment in its own right, same as a plain
    # command -- this is what lets VAR=$(cmd) qualify as a chain outside a loop too.
    assert top_level_count == 2
    assert had_compound is False


def test_inspect_refuses_assignment_with_plain_literal_value():
    assert aac._inspect("x=bar && echo hi")[0] is None


def test_inspect_refuses_assignment_mixing_literal_text_with_a_substitution():
    # r=a$(git log -1): the leading "a" is un-vetted literal text riding alongside the
    # one command this hook does check -- must still refuse, same as the for-loop's
    # mixed-source case.
    assert aac._inspect("r=a$(git log -1) && echo hi")[0] is None


def test_inspect_refuses_assignment_with_substitution_plus_trailing_literal():
    assert aac._inspect("r=$(git log -1)b && echo hi")[0] is None


def test_inspect_recurses_into_backtick_assignment_too():
    segments, _, _, reason = aac._inspect("r=`git log -1` && echo hi")
    assert reason is None
    assert segments == ["git log -1", "echo hi"]


def test_inspect_approves_assignment_inside_a_for_loop_body():
    # The exact shape that motivated this change: capture a command's output into a
    # variable, then echo it, once per loop iteration.
    segments, top_level_count, had_compound, reason = aac._inspect(
        'for b in x y; do r=$(git log --oneline -1 origin/$b); echo "$b -> $r"; done'
    )
    assert reason is None
    assert segments == [
        "git log --oneline -1 origin/$b",
        'echo $b -> $r',
    ]
    assert top_level_count == 1  # the whole for-loop is one top-level compound
    assert had_compound is True


def test_decide_approves_assignment_chain_when_nested_command_is_allowlisted():
    assert aac.decide("r=$(git log --oneline -1) && echo hi", ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_assignment_chain_when_nested_command_isnt_allowlisted():
    assert not aac.decide("r=$(git status) && echo hi", ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_assignment_with_literal_value_even_if_unrelated_chain_is_safe():
    assert not aac.decide("x=bar && echo hi", ALLOW, DENY, SAFE_DIRS)


def test_decide_approves_capture_and_echo_for_loop():
    cmd = 'for b in x y; do r=$(git log --oneline -1 origin/$b); echo "$b -> $r"; done'
    assert aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)


def test_decide_rejects_capture_and_echo_for_loop_with_unallowlisted_nested_command():
    cmd = 'for b in x; do r=$(git status); echo "$r"; done'
    assert not aac.decide(cmd, ALLOW, DENY, SAFE_DIRS)


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
