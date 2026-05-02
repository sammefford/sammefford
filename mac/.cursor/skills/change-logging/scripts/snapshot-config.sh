#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s <config-file> [reason]\n' "$(basename "$0")" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 64
fi

input_path="$1"
reason="${2:-snapshot before agent change}"

case "$input_path" in
  "~"/*) input_path="$HOME/${input_path#"~/"}" ;;
esac

if [[ "$input_path" != /* ]]; then
  input_path="$PWD/$input_path"
fi

state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
snapshot_root="${CONFIG_SNAPSHOT_DIR:-$state_home/config-snapshots}"
clean_path="${input_path#/}"
stamp="$(date +%Y%m%d-%H%M%S)"
dest_dir="$snapshot_root/$clean_path"
mkdir -p "$dest_dir"

base="$(basename "$input_path")"
dest="$dest_dir/$stamp.$base"
manifest="$snapshot_root/manifest.tsv"

if [[ -f "$input_path" ]]; then
  cp -p "$input_path" "$dest"
  status="copied"
elif [[ -e "$input_path" ]]; then
  status="skipped-non-file"
  dest=""
else
  status="missing"
  dest="$dest_dir/$stamp.MISSING"
  printf 'missing_at=%s\npath=%s\nreason=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$input_path" "$reason" > "$dest"
fi

{
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$status" \
    "$input_path" \
    "$dest" \
    "$reason"
} >> "$manifest"

if [[ -n "$dest" ]]; then
  printf '%s\n' "$dest"
else
  printf 'snapshot-config: %s is not a regular file; no snapshot copied\n' "$input_path" >&2
fi
