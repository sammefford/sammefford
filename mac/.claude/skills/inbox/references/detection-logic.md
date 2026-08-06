# Inbox Detection Logic

Kept separate from SKILL.md so query syntax can be tweaked without touching
the orchestration prompt.

## Window
Rolling last 7 days from today (inclusive).

## Email (Outlook)
Use `mcp__claude_ai_Microsoft_365__outlook_email_search` (fallback:
`mcp__ms365__list-mail-messages` with a date filter) to find Inbox messages
received in the window where Sam is a direct recipient (To or CC).

For each match, check whether Sam has a Sent-item reply in the same thread
with a timestamp after the message. If yes, exclude it (already answered).
If no, flag it.

## Slack
No dedicated "list my unread mentions/DMs" tool is exposed in this session —
only search, thread-read, and channel-read tools. Use Slack's native search
modifiers via `mcp__claude_ai_Slack__slack_search_public_and_private`:

- **DMs:** query `is:dm after:<YYYY-MM-DD>` (date = 7 days before today).
- **Mentions:** query `"@<sam's slack handle>" after:<YYYY-MM-DD>`. Read
  `references/slack-user-id.txt` first for Sam's cached user ID/handle.
  Only call `slack_read_user_profile` again if that file is missing.

For each match, use `slack_read_thread` on the parent message to check
whether Sam posted a reply with a later timestamp. If yes, exclude it. If
no, flag it.

## Why search instead of a dedicated inbox API
The Slack MCP tools available in this session don't expose a native
mentions/unread endpoint — search with modifiers is the closest equivalent.
Revisit this file if a more direct tool becomes available later.
