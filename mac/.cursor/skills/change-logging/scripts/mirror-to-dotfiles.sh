#!/usr/bin/env bash
set -euo pipefail

DOTFILES_REPO="$HOME/projects/sammefford"
DOTFILES_SUBDIR="mac"

usage() {
  printf 'Usage: %s <source-file> <commit-message>\n' "$(basename "$0")" >&2
  printf '  Copies <source-file> (must be under $HOME) to the dotfiles repo,\n' >&2
  printf '  then commits and pushes.\n' >&2
}

if [[ $# -lt 2 ]]; then
  usage
  exit 64
fi

source_file="$1"
commit_message="$2"

# Expand ~
case "$source_file" in
  "~"/*) source_file="$HOME/${source_file#"~/"}" ;;
esac

if [[ "$source_file" != /* ]]; then
  source_file="$PWD/$source_file"
fi

if [[ ! -f "$source_file" ]]; then
  printf 'mirror-to-dotfiles: source file not found: %s\n' "$source_file" >&2
  exit 1
fi

# Compute home-relative path and destination
rel_path="${source_file#"$HOME/"}"
if [[ "$rel_path" = "$source_file" ]]; then
  printf 'mirror-to-dotfiles: source file must be under $HOME\n' >&2
  exit 1
fi

dest="$DOTFILES_REPO/$DOTFILES_SUBDIR/$rel_path"
mkdir -p "$(dirname "$dest")"
cp -p "$source_file" "$dest"

cd "$DOTFILES_REPO"
git add "$DOTFILES_SUBDIR/$rel_path"

if git diff --staged --quiet; then
  printf 'mirror-to-dotfiles: no changes to commit\n'
  exit 0
fi

git commit -m "$commit_message

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

git push
printf 'mirror-to-dotfiles: mirrored %s and pushed\n' "$rel_path"
