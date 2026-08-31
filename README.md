# Instagram Reel Categorizer

A personal Telegram bot: send it an Instagram reel link and it classifies the
reel and files it as a row in a Notion database with searchable tags.

## Setup

### 1. Install
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux
```

### 2. Create the Notion database
Create a new database (full page) with these properties — names and types must
match exactly:

| Property | Type |
|----------|------|
| Title | Title |
| Category | Select |
| Tags | Multi-select |
| Caption | Text |
| Hashtags | Text |
| Author | Text |
| Post Date | Date |
| Reel URL | URL |
| Shortcode | Text |
| Date Added | Created time |
| Likes | Number |
| Thumbnail URL | URL |

(Seed a couple of `Category` options if you like — new ones are auto-added.)

### 3. Create a Notion integration
1. Go to https://www.notion.so/my-integrations → New integration → copy the
   **Internal Integration Token** → that's `NOTION_TOKEN`.
2. Open your database page → `•••` menu → **Connections** → add your integration.
3. `NOTION_DATABASE_ID` is the 32-char id in the database URL:
   `notion.so/<workspace>/<DATABASE_ID>?v=...`.

### 4. Create the Telegram bot
Message **@BotFather** → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`.

### 5. Anthropic + optional Apify
- `ANTHROPIC_API_KEY` from the Anthropic console.
- `APIFY_TOKEN` (optional) enables the paid fallback when yt-dlp is blocked.

### 6. Configure
```bash
cp .env.example .env   # then fill in the values
```
Edit `categories.json` to taste.

## Run
```bash
.venv/Scripts/python -m reel_categorizer.bot
```
Leave it running (the bot only works while this process is up). Send a reel link
in Telegram.

## Browse your reels

A local web app that shows your saved reels as clickable thumbnail tiles: one
tab per category, that category's top 3 by like count, then everything in the
category newest-first and filterable by tag. Clicking a tile opens the reel on
Instagram.

Ranking uses likes rather than views because Instagram does not expose play
counts to anonymous scrapers - yt-dlp returns `like_count` and `comment_count`
for a reel, but never `view_count`.

### Backfill older reels
Reels saved before likes and thumbnails were captured have neither. Fill them
in (add the `Likes` and `Thumbnail URL` properties to your Notion database
first):
```bash
.venv/Scripts/python -m reel_categorizer.backfill --limit 3
```
Check those three rows look right, then drop `--limit` for the rest. Each reel
needs its own Instagram fetch, so it's paced at 3s apart (`--delay`) and is
safe to re-run - anything that already succeeded is skipped. `--force`
re-fetches everything, which is also how you refresh stale like counts.

Thumbnail images are cached under `thumbnails/` because Instagram's CDN URLs
expire after a few weeks.

### Build the UI (once)
```bash
cd frontend && npm install && npm run build
```

### Run it
```bash
.venv/Scripts/python -m reel_categorizer.web
```
Then open http://127.0.0.1:8000. This reads Notion live, so it picks up new
reels on reload; it's independent of the bot process.

For frontend development, `npm run dev` in `frontend/` serves with hot reload
and proxies the API to the Python server, which needs to be running too.

## Test
```bash
.venv/Scripts/python -m pytest -q
cd frontend && npm test
```

## How it works
URL → shortcode → dedupe check → fetch metadata (yt-dlp, Apify fallback) →
Claude classifies (category + tags, reusing existing tag vocabulary) → Notion row.
New categories require a tap-to-confirm; tags are added automatically.
Each reel's like count is stored as a snapshot from save time, and its
thumbnail is downloaded to `thumbnails/` so the browser UI keeps working
after Instagram's CDN links expire.
