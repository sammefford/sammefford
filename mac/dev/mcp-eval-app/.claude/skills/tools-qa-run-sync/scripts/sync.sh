#!/usr/bin/env bash
# Mirrors one or more mcp-eval-app runs (+ results + referenced test cases)
# from the tools-qa instance into ~/mcp-eval-app-tools-qa-sync/mcp-eval-runs/.
#
# Sources MCP_EVAL_SESSION from api/.env internally so the cookie value never
# appears in this script's invocation or in any tool output/chat text.
#
# Usage:
#   sync.sh <out-subdir> <run-id> [run-id ...]
#
# Example:
#   sync.sh 6aabe366f840e08a5c832138 6aabe366f840e08a5c832138
#   sync.sh my-batch-label 66f1a2b3c4d5e6f7a8b9c0d1 66f1a2b3c4d5e6f7a8b9c0d2

set -euo pipefail

REPO_DIR="$HOME/dev/mcp-eval-app"
BASE_URL="https://mcp-eval-app-tools-qa.tools-qa.us-west-2.aws.wfk8s.com"
OUT_ROOT="$HOME/mcp-eval-app-tools-qa-sync/mcp-eval-runs"

if [[ $# -lt 2 ]]; then
  echo "Usage: sync.sh <out-subdir> <run-id> [run-id ...]" >&2
  exit 1
fi

OUT_SUBDIR="$1"
shift
RUN_ID_ARGS=()
for run_id in "$@"; do
  RUN_ID_ARGS+=(--run-id "$run_id")
done

cd "$REPO_DIR/api"
set -a
source .env
set +a

/opt/homebrew/bin/uv run python scripts/sync_run_bundle.py \
  --base-url "$BASE_URL" \
  "${RUN_ID_ARGS[@]}" \
  --out-dir "$OUT_ROOT/$OUT_SUBDIR"
