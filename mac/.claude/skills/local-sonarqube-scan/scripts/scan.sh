#!/usr/bin/env bash
# Run SonarQube Community Edition locally (Docker) to reproduce a PR/MR's
# SonarQube findings without corp login/API-token access. See ../SKILL.md.
set -euo pipefail

CONTAINER_NAME="sonar-local-scan"
PORT="9010"
STATE_DIR="${TMPDIR:-/tmp}/sonar-local-scan"
TOKEN_FILE="$STATE_DIR/token"
PASSWORD_FILE="$STATE_DIR/password"
HOST_URL="http://localhost:${PORT}"
DOCKER_HOST_URL="http://host.docker.internal:${PORT}"

usage() {
  cat <<'EOF'
Usage:
  scan.sh start
  scan.sh scan --dir DIR (--pr N | --base REF) [--key KEY] [--sources SRC]
               [--exclusions EXC] [--all]
  scan.sh stop

  start             Launch the local SonarQube server (idempotent).
  scan              Run a scan and print issues on changed lines only.
    --dir DIR         Directory to scan (e.g. services/web). Required.
    --pr N            GitHub PR number; changed lines from `gh pr diff N`.
    --base REF        Git ref to diff instead of a PR: `git diff REF...HEAD`.
    --key KEY         Sonar project key (default: local-scan).
    --sources SRC     Override sonar.sources instead of scoping via inclusions
                       (rarely needed; see SKILL.md).
    --exclusions EXC  sonar.exclusions, only applied alongside --sources.
    --all             Print every issue in touched files, not just new lines.
  stop              Remove the local SonarQube container and state.
EOF
}

cmd_start() {
  mkdir -p "$STATE_DIR"
  if docker ps --filter "name=^${CONTAINER_NAME}$" --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
    echo "Already running at $HOST_URL"
    return 0
  fi
  echo "Starting $CONTAINER_NAME on port $PORT..."
  docker run -d --name "$CONTAINER_NAME" -p "${PORT}:9000" \
    -e SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true \
    sonarqube:community >/dev/null

  echo "Waiting for SonarQube to come up (this takes 1-2 minutes)..."
  until curl -sf "$HOST_URL/api/system/status" 2>/dev/null | grep -q '"status":"UP"'; do
    sleep 5
  done

  # Fixed "Aa1!" prefix guarantees SonarQube's upper/lower/digit/special
  # complexity rule; hex suffix adds entropy. --data-urlencode below handles
  # safe transport of the special character.
  local password
  password="Aa1!$(openssl rand -hex 20)"
  local change_status
  change_status="$(curl -s -o /dev/null -w '%{http_code}' -u admin:admin \
    -X POST "$HOST_URL/api/users/change_password" \
    --data-urlencode "login=admin" \
    --data-urlencode "password=${password}" \
    --data-urlencode "previousPassword=admin")"
  if [[ "$change_status" != "204" ]]; then
    echo "Failed to set local admin password (HTTP $change_status)." >&2
    exit 1
  fi
  echo "$password" > "$PASSWORD_FILE"
  chmod 600 "$PASSWORD_FILE"

  local token_response
  token_response="$(curl -s -u "admin:${password}" -X POST "$HOST_URL/api/user_tokens/generate" \
    --data-urlencode "name=local-scan-$$")"
  if ! echo "$token_response" | python3 -c "import json,sys; json.load(sys.stdin)['token']" 2>/dev/null; then
    echo "Failed to generate scanner token: $token_response" >&2
    exit 1
  fi
  echo "$token_response" | python3 -c "import json,sys; print(json.load(sys.stdin)['token'])" > "$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"

  echo "Ready at $HOST_URL (local-only admin account; credentials never leave this machine)."
}

cmd_stop() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
  rm -rf "$STATE_DIR"
  echo "Stopped and cleaned up."
}

cmd_scan() {
  local dir="" pr="" base="" key="local-scan" sources="" exclusions="" show_all=0

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dir) dir="$2"; shift 2 ;;
      --pr) pr="$2"; shift 2 ;;
      --base) base="$2"; shift 2 ;;
      --key) key="$2"; shift 2 ;;
      --sources) sources="$2"; shift 2 ;;
      --exclusions) exclusions="$2"; shift 2 ;;
      --all) show_all=1; shift ;;
      *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
    esac
  done

  [[ -z "$dir" ]] && { echo "--dir is required" >&2; exit 1; }
  [[ -z "$pr" && -z "$base" ]] && { echo "one of --pr or --base is required" >&2; exit 1; }
  [[ ! -f "$TOKEN_FILE" ]] && { echo "Run 'scan.sh start' first." >&2; exit 1; }

  local token; token="$(cat "$TOKEN_FILE")"
  local diff_file="$STATE_DIR/pr.diff"

  if [[ -n "$pr" ]]; then
    gh pr diff "$pr" --patch > "$diff_file"
  else
    git diff "${base}...HEAD" > "$diff_file"
  fi

  # Map of file -> sorted added (new-file) line numbers, scoped to --dir and
  # stripped of the --dir prefix so paths match sonar's dir-relative output.
  python3 - "$diff_file" "$dir" "$STATE_DIR/added_lines.json" <<'PYEOF'
import re, sys, json

diff_path, scan_dir, out_path = sys.argv[1], sys.argv[2].rstrip("/") + "/", sys.argv[3]
current_file = None
new_line = None
added = {}

with open(diff_path) as f:
    for line in f:
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if m:
            new_line = int(m.group(1))
            continue
        if current_file is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if current_file.startswith(scan_dir):
                rel = current_file[len(scan_dir):]
                added.setdefault(rel, set()).add(new_line)
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            pass
        elif not line.startswith("\\"):
            new_line += 1

json.dump({k: sorted(v) for k, v in added.items()}, open(out_path, "w"))
PYEOF

  # Scope the scan to exactly the changed files via sonar.inclusions, rather
  # than overriding sonar.sources — a repo's own sonar-project.properties
  # (if present in --dir) usually separates sonar.sources/sonar.tests
  # carefully, and forcing sonar.sources="." collides with it (a file gets
  # "indexed twice" as both main and test code). Inclusions narrow within
  # whatever source/test split already exists.
  local inclusions
  inclusions="$(python3 -c "
import json
added = json.load(open('$STATE_DIR/added_lines.json'))
print(','.join(sorted(added.keys())))
")"

  if [[ -z "$inclusions" ]]; then
    echo "No changed files found under $dir for this diff."
    return 0
  fi

  local -a scanner_args=(
    -Dsonar.host.url="$DOCKER_HOST_URL"
    -Dsonar.projectKey="$key"
    -Dsonar.projectName="$key"
    -Dsonar.inclusions="$inclusions"
    -Dsonar.sourceEncoding=UTF-8
  )
  # Only override sonar.sources if the caller asked to, or the target dir has
  # no properties file of its own to fall back on.
  if [[ -n "$sources" ]]; then
    scanner_args+=(-Dsonar.sources="$sources")
  elif [[ ! -f "$dir/sonar-project.properties" ]]; then
    scanner_args+=(-Dsonar.sources=.)
  fi
  [[ -n "$exclusions" ]] && scanner_args+=(-Dsonar.exclusions="$exclusions")

  echo "Scanning $(echo "$inclusions" | tr ',' '\n' | wc -l | tr -d ' ') changed file(s) under $dir (project key: $key)..."
  ( cd "$dir" && docker run --rm \
      -v "$(pwd)":/usr/src \
      --add-host=host.docker.internal:host-gateway \
      -e SONAR_TOKEN="$token" \
      sonarsource/sonar-scanner-cli \
      "${scanner_args[@]}" )

  echo "Waiting for analysis to process..."
  for _ in $(seq 1 60); do
    status="$(curl -s -u "admin:$(cat "$PASSWORD_FILE")" \
      "$HOST_URL/api/ce/component?component=$key" \
      | python3 -c "import json,sys
d=json.load(sys.stdin)
t=d.get('current')
print(t['status'] if t else 'PENDING')" 2>/dev/null || echo PENDING)"
    [[ "$status" == "SUCCESS" ]] && break
    sleep 3
  done

  curl -s -u "admin:$(cat "$PASSWORD_FILE")" \
    "$HOST_URL/api/issues/search?componentKeys=${key}&resolved=false&ps=500" \
    > "$STATE_DIR/issues.json"

  python3 - "$STATE_DIR/issues.json" "$STATE_DIR/added_lines.json" "$show_all" <<'PYEOF'
import json, sys

issues_path, added_path, show_all = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
issues = json.load(open(issues_path))["issues"]
added = json.load(open(added_path))

def on_added_line(issue):
    comp = issue["component"].split(":", 1)[-1]
    line = issue.get("line")
    return comp in added and line in added[comp]

selected = issues if show_all else [i for i in issues if on_added_line(i)]

label = "all issues in touched files" if show_all else "issues on PR/MR-added lines"
print(f"\n{len(selected)} {label} (of {len(issues)} total in scanned files):\n")
for i in selected:
    comp = i["component"].split(":", 1)[-1]
    print(f"[{i.get('severity')}] {comp}:{i.get('line')} {i['rule']}")
    print(f"    {i['message']}")
PYEOF
}

case "${1:-}" in
  start) cmd_start ;;
  scan) shift; cmd_scan "$@" ;;
  stop) cmd_stop ;;
  *) usage; exit 1 ;;
esac
