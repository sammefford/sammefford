---
name: download-sources
description: Download source material (PDF, PPTX, HTML, VTT, MD, TXT, Slack threads, Teams meetings) from a list of URLs into a local folder for later summarization. Handles internal Adobe systems (wiki, Slack) via Chrome DevTools with the user's existing browser session.
user-invocable: true
---

# Download Sources

Downloads all source material linked in a markdown file or message into a local folder. Output is raw files suitable for `/pyramid-summarize`.

## Arguments

- `<source-md>` — path to or inline text of the markdown containing links (required if links aren't in the message)
- `--output <folder>` — destination folder for downloaded files (required). Created if missing.
- `--types <ext,...>` — optional filter; defaults to all supported types

---

## Step 0 — Parse all links

Extract every hyperlink from the source text. For each link record:
- URL
- Anchor text (use as filename hint)
- Inferred type: wiki | slack | teams | pdf | pptx | vtt | html | md | txt | other

Produce a deduplicated list (same URL appearing as multiple source citations counts once).

---

## Step 1 — Create output folder and subfolders

```bash
mkdir -p "<output>/wiki"
mkdir -p "<output>/slack"
mkdir -p "<output>/teams"
mkdir -p "<output>/files"
```

---

## Step 2 — Download by type

Work through all links using TodoWrite. Mark each complete immediately. Run independent downloads in parallel where possible.

### 2a — Adobe Wiki pages (wiki.corp.adobe.com)

These require the user's browser session. Use Chrome DevTools.

For each wiki URL:

1. Navigate Chrome to the URL:
```
mcp__chrome-devtools__navigate_page(type="url", url="<wiki-url>")
```

2. Wait for the page to fully render (check for main content area):
```
mcp__chrome-devtools__take_snapshot()
```
If the page shows a login screen, pause and ask the user to log in, then retry.

3. Extract the full rendered HTML (including inline styles and expanded sections):
```javascript
() => document.documentElement.outerHTML
```

4. Extract all image URLs referenced on the page:
```javascript
() => Array.from(document.querySelectorAll('img')).map(i => i.src).filter(s => s.startsWith('http'))
```

5. Download each image from the browser context using fetch, base64-encode it, and embed it OR save it as a sidecar file. For wiki pages, saving the HTML with relative image paths is acceptable — the images provide context for the pyramid summarizer.

6. Save HTML to `<output>/wiki/<slug>.html` where slug is derived from the page title or URL path.

7. For each image: download via browser fetch and save to `<output>/wiki/<slug>_files/<filename>`.

8. Rewrite image `src` attributes in the saved HTML to point to the local `<slug>_files/` sidecar folder (matching Chrome's "Webpage, Complete" structure).

**Slug derivation:** lowercase the last path segment of the URL, replace `+` and `%20` with `-`, strip leading numbers like `3323606907` if followed by a name, use the name part. Example: `3323606907/LangSmith+Onboarding` → `langsmith-onboarding`.

---

### 2b — Slack threads (adobe.enterprise.slack.com)

These require the user's Slack session in Chrome.

For each Slack URL:

1. Navigate Chrome to the URL and wait for messages to load.
2. Scroll to the top of the thread to load history (`mcp__chrome-devtools__evaluate_script` with `window.scrollTo(0,0)` then wait).
3. Scroll down incrementally to trigger lazy-loaded messages.
4. Extract all message elements:
```javascript
() => {
  const msgs = document.querySelectorAll('[data-qa="message_container"]');
  return Array.from(msgs).map(m => ({
    sender: m.querySelector('[data-qa="message_sender_name"]')?.innerText,
    time: m.querySelector('[data-qa="message_time"]')?.getAttribute('aria-label'),
    text: m.querySelector('.c-message_kit__blocks')?.innerText
  }));
}
```
5. Format as a markdown file and save to `<output>/slack/<channel-id>-<message-id>.md`.

If the above selector fails (Slack updates its DOM frequently), fall back to:
- `mcp__chrome-devtools__take_snapshot()` — parse the a11y tree for message content
- Screenshot as last resort

---

### 2c — Microsoft Teams meeting links

For each Teams link:
1. Navigate Chrome to the meeting URL and sign in if prompted.
2. Look for "Chat" and "Transcript" tabs in the meeting recap view.
3. For chat: extract message list as markdown, save to `<output>/teams/<meeting-id>-chat.md`.
4. For transcript (.vtt): look for a download button or use:
```javascript
() => {
  const links = document.querySelectorAll('a[href$=".vtt"], a[download]');
  return Array.from(links).map(l => l.href);
}
```
Then download the .vtt file and save to `<output>/teams/<meeting-id>.vtt`.

If the meeting is not yet recorded or transcript is unavailable, note it in the final report.

---

### 2d — Direct file links (PDF, PPTX, VTT, DOCX, TXT, MD)

For publicly accessible or already-authenticated files:

```bash
curl -L -b cookies.txt -o "<output>/files/<filename>" "<url>"
```

If the file requires browser auth, instead:
1. Navigate Chrome to the URL — the browser will handle auth and either display or download the file.
2. If displayed in browser (PDF viewer): use `evaluate_script` to trigger `window.print()` or find the download button.
3. If auto-downloaded: check the user's Downloads folder and move to `<output>/files/`.

---

### 2e — Generic HTML pages (non-wiki)

For any other HTML URL:

Option A (preferred — uses existing session):
1. Navigate Chrome to the URL.
2. Extract HTML via `evaluate_script(() => document.documentElement.outerHTML)`.
3. Extract and download images.
4. Save as `<output>/files/<slug>.html` with a `<slug>_files/` sidecar.

Option B (public pages only):
```bash
wget --page-requisites --convert-links --no-parent \
  --directory-prefix="<output>/files/<slug>_files" \
  --restrict-file-names=windows \
  "<url>"
```

---

## Step 3 — Don't give up easily

For each URL that fails on first attempt:
1. Check if the page requires login — ask the user to authenticate in Chrome, then retry.
2. Check if the page is behind a VPN — ask the user if VPN is active.
3. Try an alternative approach (screenshot + OCR via snapshot if HTML extraction fails).
4. If a page has been deleted or is genuinely inaccessible, note it in the report but continue with others.

---

## Step 4 — Write a download manifest

After all downloads complete, write `<output>/MANIFEST.md`:

```markdown
# Download Manifest
Generated: <date>

## Downloaded
| File | Source URL | Type | Notes |
|------|-----------|------|-------|

## Skipped / Failed
| URL | Reason |
|-----|--------|
```

---

## Step 5 — Report to user

- Count of files downloaded by type
- List of any failures with reasons
- Location of MANIFEST.md
- Reminder: run `/pyramid-summarize <output>` next to generate summaries
