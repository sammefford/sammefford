#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s <category> <summary> -- <command> [args...]\n' "$(basename "$0")" >&2
}

if [[ $# -lt 4 || "${3:-}" != "--" ]]; then
  usage
  exit 64
fi

category="$1"
summary="$2"
shift 3

safe_category="$(printf '%s' "$category" | tr -c '[:alnum:]_.-' '_' | sed 's/^_*//; s/_*$//')"
[[ -n "$safe_category" ]] || safe_category="change"

state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
log_root="${AGENT_CHANGE_LOG_DIR:-$state_home/agent-change-log}"
date_dir="$(date +%Y-%m-%d)"
stamp="$(date +%H%M%S)"
log_dir="$log_root/$date_dir"
mkdir -p "$log_dir"

log_file="$log_dir/${stamp}-${safe_category}-$$.log"

quote_command() {
  local arg
  for arg in "$@"; do
    printf '%q ' "$arg"
  done
}

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"

{
  printf 'started_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'category=%s\n' "$category"
  printf 'summary=%s\n' "$summary"
  printf 'cwd=%s\n' "$PWD"
  printf 'repo_root=%s\n' "$repo_root"
  printf 'command='
  quote_command "$@"
  printf '\n\n'
} > "$log_file"

printf 'Logging command output to %s\n' "$log_file" >&2

set +e
"$@" > >(tee -a "$log_file") 2> >(tee -a "$log_file" >&2)
exit_code=$?
set -e

{
  printf '\nfinished_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'exit_code=%s\n' "$exit_code"
} >> "$log_file"

exit "$exit_code"
