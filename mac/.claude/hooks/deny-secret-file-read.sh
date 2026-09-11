#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash, no "if" scoping — runs on every Bash call).
# Denies any command whose argument text names a secret-bearing file
# (.env*, .npmrc, *.pem, *.key, or anything with "credential" in the name).
# These can't be enumerated as finite Bash(...) allow-prefixes since cat,
# head, less, sed -n, python3 -c "open(...)", etc. can all read them.
#
# Exception: scripts/with-env.sh is renzler-service's own sanctioned pattern for
# sourcing .env into a subprocess's env without ever printing its contents (see
# that script's own header comment: "Agents: use this to run tools after the
# USER has populated .env locally"). A command is only treated as a safe
# with-env.sh invocation if it has NO shell metacharacters anywhere (;, &, |,
# backtick, $(, <, >, control chars) — so nothing can be chained/smuggled
# before or after it — and the whole command (after optional leading
# VAR=value assignments) is exactly a with-env.sh call. Anything else
# (including with-env.sh combined with another command via ; or &&) falls
# through to the secret_pattern deny check below, unchanged.
#
# Exception: the checking-env-var-presence skill's check_env_vars.sh only
# reports presence/absence of var names via grep -c counts — it never prints
# matched line content or values, so passing it a .env/.npmrc path is safe.
# Same no-metacharacter anchoring as with-env.sh above, to prevent smuggling.
cmd=$(jq -r '.tool_input.command // empty')

no_meta_pattern='[;&|`$<>[:cntrl:]]'
with_env_anchor='^([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*([^[:space:]]*/)?with-env\.sh([[:space:]].*)?$'
check_env_vars_anchor='^([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*([^[:space:]]*/)?check_env_vars\.sh([[:space:]].*)?$'

if ! printf '%s' "$cmd" | grep -Eq -- "$no_meta_pattern" && printf '%s' "$cmd" | grep -Eq -- "$with_env_anchor"; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"scripts/with-env.sh is renzler-service'"'"'s sanctioned pattern for sourcing .env into a subprocess without exposing its contents."}}'
  exit 0
fi

if ! printf '%s' "$cmd" | grep -Eq -- "$no_meta_pattern" && printf '%s' "$cmd" | grep -Eq -- "$check_env_vars_anchor"; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"checking-env-var-presence'"'"'s check_env_vars.sh only reports presence/absence via grep counts, never values."}}'
  exit 0
fi

secret_pattern='(^|[^A-Za-z0-9_.-])(\.env([.][A-Za-z0-9_-]+)?|\.npmrc|[A-Za-z0-9_.-]*\.(pem|key)|[A-Za-z0-9_.-]*credential[A-Za-z0-9_.-]*)($|[^A-Za-z0-9_.-])'

if printf '%s' "$cmd" | grep -Eqi -- "$secret_pattern"; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Command references a secret-bearing file (.env/.npmrc/*.pem/*.key/credentials) — blocked to avoid exposing secret contents."}}'
fi
