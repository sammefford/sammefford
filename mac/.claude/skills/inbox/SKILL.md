---
name: inbox
description: Use when checking which emails or Slack messages from the last week are still awaiting a reply, or when a triage report of unanswered threads with suggested reply drafts is needed. Read/draft only, never sends or posts.
---

# Inbox Triage

Flags email and Slack messages from the last 7 days where Sam hasn't
replied yet, and drafts a suggested reply for each. **Read/draft only —
never sends or posts anything.**

## Tool scoping (hard requirement)
This skill's work uses read/search/draft tools only:
`mcp__claude_ai_Microsoft_365__outlook_email_search`, `mcp__ms365__list-mail-messages`,
`mcp__ms365__get-mail-message`, `mcp__claude_ai_Slack__slack_search_public_and_private`,
`slack_read_thread`, `slack_read_channel`, `slack_read_user_profile`,
`slack_send_message_draft` (drafts only, does not deliver).
**Never call** `slack_send_message`, `slack_schedule_message`, or any
Outlook/Graph send/reply-send tool. If dispatching a subagent to do this
work, scope its tool access to exclude every send-capable tool explicitly.

## Caching — read before any live lookup
- `references/slack-user-id.txt` — Sam's resolved Slack user ID and
  handle. Read this file first. Only call `slack_read_user_profile` again
  if the file is missing or a query using the cached handle fails
  unexpectedly.

## Detection logic
See `references/detection-logic.md` for the exact search queries and the
reply-detection rule.

## Procedure
1. Compute the window: today back 7 days.
2. Run the email and Slack searches per `references/detection-logic.md`.
3. For each flagged thread, draft a 2–4 sentence suggested reply matching
   Sam's usual tone (terse, direct). Draft only — never send.
4. Write the full report to
   `~/.claude/skills/inbox/reports/YYYY-MM-DD.md` (today's date;
   **overwrite** if it already exists — reruns replace, they don't
   append), oldest-flagged-first, with `## Emails` and `## Slack` section
   headers, each entry formatted:
   ```
   - **[Slack/Email] From: <sender> — <subject/channel>** (age: 3d)
     Context: <one-line summary of what they need>
     Suggested reply: "<draft text>"
   ```
5. Reply in chat with a short summary: counts flagged by source, and the
   report file path.

## Error handling
If a search tool fails (auth expired, etc.), record a one-line error for
that source in the report and continue with whatever succeeded. Never
silently drop a source or retry-and-hide the failure.
