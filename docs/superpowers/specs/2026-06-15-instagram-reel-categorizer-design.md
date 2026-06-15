# Instagram Reel Categorizer — Design

**Date:** 2026-06-15
**Status:** Approved (design phase)

## Summary

A personal Telegram bot that accepts Instagram Reel links, extracts each reel's
text metadata (caption, hashtags, author, post date), classifies it into one of a
fixed-but-growable set of categories using Claude, attaches searchable free-form
tags, and files the result as a row in a Notion database. Designed to start simple
(text-metadata only) and remain extensible toward richer analysis (video frames,
audio) later.

## Goals

- Send a reel link to a Telegram bot from any device; get it auto-filed in Notion.
- Classify into **one** category from a fixed list; propose new categories with
  explicit user approval.
- Attach **3–6 searchable tags** per reel, automatically, while keeping the tag
  vocabulary canonical (no semantically-duplicate tags).
- Keep Instagram data-fetching swappable and resilient (free tools first, paid
  API fallback).

## Non-Goals (for v1)

- Video frame analysis or audio transcription (designed for later, not built now).
- 24/7 cloud hosting (runs locally; only processes while the PC + script are up).
- Per-tag approval prompts (tags are fully automatic).
- A web UI (Notion *is* the browsing UI).

## Architecture

Single local Python process running a Telegram bot via **long-polling**, structured
as a pipeline of isolated, independently-testable modules.

### Flow

```
Telegram message (reel URL)
  → parse + validate URL, extract shortcode
  → dedupe check against Notion (by shortcode)
  → fetch metadata (yt-dlp → paid API fallback)  → ReelMetadata
  → classify (Claude Haiku 4.5) using category list + existing tag vocabulary
        → { category | proposed_new_category, tags[], reason }
  → if proposed new category: reply with inline [Add & file] / [Pick existing] / [Skip]
  → write row to Notion (category, tags, metadata)
  → reply confirming category + tags
```

### Components

| Module | Responsibility | External deps |
|---|---|---|
| `bot.py` | Telegram handlers, orchestration, inline-button flow | python-telegram-bot |
| `models.py` | `ReelMetadata` dataclass — normalized shape all fetchers return | — |
| `urls.py` | Validate IG reel URLs, extract shortcode | — |
| `fetchers/base.py` | `MetadataFetcher` interface | — |
| `fetchers/ytdlp_fetcher.py` | Primary fetcher via yt-dlp | yt-dlp |
| `fetchers/apify_fetcher.py` | Paid fallback fetcher | requests/apify |
| `fetchers/__init__.py` | `get_metadata(url)` — tries fetchers in order, returns first success | — |
| `classifier.py` | One Claude call → category + tags + reason | anthropic |
| `notion_store.py` | Dedupe lookup, read tag vocabulary, write row, add category/tag options | notion-client |
| `config.py` | Load `categories.json` + `.env` | — |

Each module answers cleanly: what it does, how it's used, what it depends on.
External calls (IG, Anthropic, Notion) sit behind narrow interfaces so they mock
easily in tests and swap without touching orchestration.

## Data Model

### `ReelMetadata` (normalized)

```
shortcode:  str            # e.g. "C1a2b3c4d5"
url:        str            # canonical reel URL
caption:    str            # full caption text ("" if none)
hashtags:   list[str]      # parsed from caption, lowercased, no "#"
author:     str            # uploader username
post_date:  date | None    # original post date if available
source:     str            # which fetcher succeeded ("ytdlp" | "apify")
```

### Notion database properties

| Property | Type | Notes |
|---|---|---|
| Title | title | Caption snippet (first ~80 chars) or author if no caption |
| Category | select | One of the approved categories |
| Tags | multi-select | 3–6 auto tags; the living tag vocabulary |
| Caption | rich_text | Full caption |
| Hashtags | rich_text | Space-joined original hashtags |
| Author | rich_text | Uploader username |
| Post Date | date | Original post date |
| Reel URL | url | Canonical link |
| Shortcode | rich_text | Dedupe key |
| Date Added | created_time | Auto |

## Classification

- **Model:** Claude **Haiku 4.5** (`claude-haiku-4-5-20251001`) — cheap, fast, ample
  for text classification. (Confirm exact model id / params against the `claude-api`
  skill at implementation time.)
- **Prompt input:** approved category list; the **existing tag vocabulary** read
  live from Notion; the reel's caption, hashtags, author, post date.
- **Output (structured):** `{ category, is_new_category: bool, tags: [...], reason }`.
  Parsed from a JSON response (tool-use / structured output preferred over free text).
- **Category rule:** pick the best fit from the list. If nothing fits well, set
  `is_new_category: true` and put the proposed name in `category` — this triggers
  the approval flow rather than silently guessing.
- **Tag rule (canonicalization):** *Always reuse an existing tag when it is
  semantically equivalent to what you'd otherwise write* (prefer existing `budget`
  over new `low-cost`). Only mint a new tag when nothing existing means the same
  thing. Tags are lowercase, kebab-case, 3–6 per reel.

## Category Growth (suggest-new flow)

When `is_new_category` is true, the bot replies with an inline keyboard:

- **[Add "X" & file]** → append `X` to `categories.json`, add it as a Notion
  Category select option, then write the row.
- **[Pick existing…]** → show the current categories as buttons; file under the
  chosen one.
- **[Skip]** → file under `Uncategorized` (auto-created if absent) so nothing is lost.

Categories grow **deliberately** (human-approved). Tags grow **freely** but stay
canonical via vocabulary reuse.

## Tag Consistency

1. Before classifying, `notion_store` reads the current Tags multi-select options
   — the canonical vocabulary.
2. That vocabulary is injected into the classifier prompt with the reuse instruction
   above, so the model snaps to existing tags instead of inventing synonyms.
3. New tags are written straight to the Notion multi-select (auto-added).
4. **Future hook (not built now):** optional `tag_aliases.json` mapping stray
   synonyms to canonical tags (e.g. `low-cost → budget`), applied post-classification.

## Dedupe

Extract shortcode from the URL and query Notion for an existing row with that
shortcode. If found, reply *"already saved under <category>"* and skip. Prevents
duplicate rows when the same reel is sent twice.

## Error Handling

- **URL invalid / not a reel:** reply with a short usage hint.
- **Both fetchers fail:** reply with the error; offer to accept a manual one-line
  note so the link is still captured (filed as `Uncategorized` with the note).
- **Anthropic call fails:** reply with a transient-error message; do not write a
  partial row. User can resend.
- **Notion write fails:** reply with the error; nothing silently dropped.
- **Low-confidence classification:** handled by the suggest-new flow (propose new
  rather than guess).

## Configuration

- `categories.json` — seeded list: `Food Recipes`, `Food Places`, `Fitness`,
  `Tech`, `Sports`, `Gaming`. User-editable.
- `.env` — secrets: `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`, `NOTION_TOKEN`,
  `NOTION_DATABASE_ID`, optional `APIFY_TOKEN` (enables paid fallback).
- `.env.example` committed; real `.env` gitignored.

## Testing (TDD)

Unit tests with all external calls mocked:

- `urls.py` — valid/invalid URL parsing, shortcode extraction (reel/reels/share forms).
- `fetchers` — normalization of raw yt-dlp JSON → `ReelMetadata`; fallback ordering
  (primary fails → secondary tried); both-fail behavior.
- `classifier.py` — prompt includes categories + vocabulary; correct parsing of
  category / is_new_category / tags from a mocked Anthropic response.
- `notion_store.py` — dedupe hit/miss, row payload shape, new category/tag option
  creation (mocked client).
- `bot.py` — orchestration happy path and the suggest-new branch (mocked deps).

## Tech Stack

Python 3.11+, `python-telegram-bot`, `yt-dlp`, `anthropic`, `notion-client`,
`pytest` (+ `pytest-asyncio`), `python-dotenv`.

## Future Extensions (explicitly deferred)

- Video frame sampling + vision model; audio transcription (the "start simple"
  upgrade path — fetchers and `ReelMetadata` are shaped to absorb new fields).
- `tag_aliases.json` canonicalization map.
- Cloud/webhook hosting for 24/7 uptime.
