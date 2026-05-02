#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s <category> <target> <summary>\n' "$(basename "$0")" >&2
}

if [[ $# -lt 3 ]]; then
  usage
  exit 64
fi

category="$1"
target="$2"
summary="$3"

state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
log_root="${AGENT_CHANGE_LOG_DIR:-$state_home/agent-change-log}"
mkdir -p "$log_root"

timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
changelog="$log_root/CHANGELOG.md"
tsv="$log_root/changes.tsv"

if [[ ! -f "$changelog" ]]; then
  printf '# Agent Change Log\n\n' > "$changelog"
fi

{
  printf '## %s\n\n' "$timestamp"
  printf -- '- Category: `%s`\n' "$category"
  printf -- '- Target: `%s`\n' "$target"
  printf -- '- Summary: %s\n' "$summary"
  printf -- '- CWD: `%s`\n' "$PWD"
  if [[ -n "$repo_root" ]]; then
    printf -- '- Repo: `%s`\n' "$repo_root"
  fi
  printf '\n'
} >> "$changelog"

printf '%s\t%s\t%s\t%s\t%s\n' "$timestamp" "$category" "$target" "$summary" "$PWD" >> "$tsv"
printf '%s\n' "$changelog"
