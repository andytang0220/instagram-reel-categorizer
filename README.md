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

## Test
```bash
.venv/Scripts/python -m pytest -q
```

## How it works
URL → shortcode → dedupe check → fetch metadata (yt-dlp, Apify fallback) →
Claude classifies (category + tags, reusing existing tag vocabulary) → Notion row.
New categories require a tap-to-confirm; tags are added automatically.
