---
name: local-sonarqube-scan
description: Use when a PR or MR shows a failing, advisory, or otherwise unreachable SonarQube/static-analysis check and there's no login, account, or API token for the hosted SonarQube instance, or the issues API returns 401. Also use to check for new SonarQube-style findings before opening a PR. Triggers include SonarQube check failed, quality gate, static analysis red, no sonar token, sonarqube login required, can't reach corp sonarqube, reproduce Sonar findings locally.
---

# Local SonarQube Scan

## Overview

Run SonarQube Community Edition in Docker on your own machine to reproduce a PR/MR's SonarQube findings — no corp login, account, or API token required, and nothing is uploaded anywhere. Useful when the hosted instance is login-walled, when you want a Sonar-style report before opening the PR, or to confirm a fix actually clears a reported finding.

## When to use

- A PR/MR's SonarQube (or "static analysis") check is failing or advisory-red and you need to know exactly what it flagged, but you have no corp SonarQube credentials.
- The SonarQube API returns 401 and there's no `SONAR_TOKEN` configured for the session.
- You want to check for new Sonar-style issues before opening a PR.
- You fixed a reported Sonar finding and want to confirm it's resolved before pushing.

Don't use this as a substitute for the corp Sonar quality gate in a merge decision — it uses SonarQube's default "Sonar way" profile, which may not match the corp instance's custom rules, severities, or thresholds exactly.

## Key insight: filter to new-code lines

A scan of a whole file reports every pre-existing issue in it, not just what the PR introduced — SonarQube's own PR decoration only reports issues on lines the PR actually changed ("new code"). A large pre-existing file can dump 100+ unrelated findings if you don't filter. `scripts/scan.sh` handles this automatically by cross-referencing results against the PR/MR diff.

## Quick start

```bash
~/.claude/skills/local-sonarqube-scan/scripts/scan.sh start
~/.claude/skills/local-sonarqube-scan/scripts/scan.sh scan --dir services/web --pr 5602
# ...fix what it finds, then re-run scan to confirm...
~/.claude/skills/local-sonarqube-scan/scripts/scan.sh stop
```

Use `--base origin/main` instead of `--pr N` when there's no GitHub PR (e.g. a GitLab MR, or before a PR exists) — it diffs `REF...HEAD` with plain `git diff` instead of `gh pr diff`.

`scan` prints only issues on lines the diff added or modified. Pass `--all` to see every issue in the touched files instead (useful for spot-checking one file in depth). Full usage: `scan.sh` with no args.

## How it works

1. `start` launches `sonarqube:community` in Docker (port 9010), waits for `UP`, sets a random local-only admin password, and generates a scanner token. Everything is self-contained on your machine; nothing touches the corp instance.
2. `scan` computes the diff (`gh pr diff N --patch` or `git diff REF...HEAD`) and works out exactly which (file, line) pairs were added.
3. It runs `sonarsource/sonar-scanner-cli` in Docker against `--dir`, scoped via `sonar.inclusions` to just the changed files, pointed at the local server through `host.docker.internal`.
4. It queries `/api/issues/search` on the local server and keeps only issues whose (file, line) is in the added-lines set.
5. `stop` removes the container and the local state (token, password, diff cache).

## Common mistakes

- **Reporting every issue instead of the new ones**: skipping the added-lines filter. Always use `scan.sh` rather than a raw scan, or you'll see dozens of pre-existing issues alongside the real ones.
- **Overriding `sonar.sources` when the target dir already has its own `sonar-project.properties`**: forcing `sonar.sources=.` collides with that file's `sonar.tests` split and SonarQube fails with "file can't be indexed twice." Scope via `sonar.inclusions` (what `scan.sh` does) instead of overriding sources — inclusions narrow within whatever source/test split already exists.
- **`localhost:9010` unreachable from inside the scanner container**: the scanner runs in its own container; use `http://host.docker.internal:9010`, not `localhost`.
- **Password rejected when scripting the admin account**: SonarQube enforces upper/lower/digit/special-character complexity on `change_password` — a plain hex or base64 string can fail this. `scan.sh` prefixes a fixed `Aa1!` to satisfy it.
- **Passing secrets through curl's raw `-d`**: it does not URL-encode, so a `+` in a generated password is read back as a space by the server, silently breaking the very next authenticated call. Use `--data-urlencode` for any generated credential.
- **Renamed/moved files inflate the "added lines" set**: a plain diff without rename detection treats a moved-and-edited file as fully deleted + fully added, so every line looks "new." The corp Sonar's real PR decoration does rename-aware SCM blame and won't have this problem — treat local over-counting on moved files as a known false-positive risk, not a bug to chase.
- **Corp custom rules aren't in the local profile**: this uses SonarQube's out-of-the-box "Sonar way" profile, so severities and rule sets may differ from what the corp dashboard reports.

## Cleanup

`scan.sh stop` removes the container and all local state (token, password, cached diff). Nothing persists between sessions by design — run `start` again next time.
