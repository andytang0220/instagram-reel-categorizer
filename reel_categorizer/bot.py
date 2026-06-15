from __future__ import annotations

import asyncio
import re
import uuid

from notion_client import Client as NotionClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .classifier import Classifier, anthropic_completion_fn
from .config import add_category, load_categories, load_settings
from .fetchers.apify_fetcher import ApifyFetcher
from .fetchers.ytdlp_fetcher import YtdlpFetcher
from .notion_store import NotionStore
from .pipeline import Pipeline

_URL_RE = re.compile(r"https?://\S+")

HELP = (
    "Send me an Instagram reel link and I'll file it in Notion.\n"
    "I pick a category and add searchable tags automatically."
)


def extract_urls(text: str | None) -> list[str]:
    return _URL_RE.findall(text or "")


def build_pipeline(settings) -> Pipeline:
    fetchers = [YtdlpFetcher(), ApifyFetcher(settings.apify_token)]
    classifier = Classifier(anthropic_completion_fn(settings.anthropic_api_key))
    store = NotionStore(
        NotionClient(auth=settings.notion_token), settings.notion_database_id
    )
    return Pipeline(fetchers, classifier, store, load_categories)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    urls = [u for u in extract_urls(update.message.text) if "instagram.com" in u]
    if not urls:
        await update.message.reply_text("Send me an Instagram reel link.")
        return
    pipeline: Pipeline = context.application.bot_data["pipeline"]
    for url in urls:
        result = pipeline.process(url)
        if result.kind == "needs_category":
            token = uuid.uuid4().hex[:8]
            context.application.bot_data.setdefault("pending", {})[token] = (
                result.meta, result.tags, result.proposed_category, result.title)
            categories = load_categories()
            keyboard = [[InlineKeyboardButton(
                f'Add "{result.proposed_category}" & file',
                callback_data=f"add:{token}")]]
            keyboard += [
                [InlineKeyboardButton(c, callback_data=f"pick:{token}:{i}")]
                for i, c in enumerate(categories)
            ]
            keyboard.append([InlineKeyboardButton(
                "Skip (Uncategorized)", callback_data=f"skip:{token}")])
            await update.message.reply_text(
                f"{result.message}\nChoose a category:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            suffix = (" · tags: " + ", ".join(result.tags)) if result.tags else ""
            await update.message.reply_text(result.message + suffix)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    pipeline: Pipeline = context.application.bot_data["pipeline"]
    pending = context.application.bot_data.get("pending", {})
    parts = query.data.split(":")
    action, token = parts[0], parts[1]
    entry = pending.get(token)
    if not entry:
        await query.edit_message_text("That request expired — send the link again.")
        return
    meta, tags, proposed, title = entry
    try:
        if action == "add":
            add_category(proposed)
            pipeline.save(meta, proposed, tags, title)
            await query.edit_message_text(f"Added category “{proposed}” and saved.")
        elif action == "pick":
            category = load_categories()[int(parts[2])]
            pipeline.save(meta, category, tags, title)
            await query.edit_message_text(f"Saved to {category}.")
        else:  # skip
            pipeline.save(meta, "Uncategorized", tags, title)
            await query.edit_message_text("Saved to Uncategorized.")
    except Exception as exc:  # noqa: BLE001 - surface save/Notion failures to the user
        await query.edit_message_text(f"Couldn't save to Notion: {exc}")
    finally:
        pending.pop(token, None)


def main() -> None:
    # python-telegram-bot v21 calls asyncio.get_event_loop(), which raises on
    # Python 3.12+ when no loop is set. Ensure one exists before run_polling().
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    settings = load_settings()
    app = Application.builder().token(settings.telegram_token).build()
    app.bot_data["pipeline"] = build_pipeline(settings)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
