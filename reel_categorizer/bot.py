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
from .config import (
    add_category, load_categories, load_settings, match_category, remove_category)
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


async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cats = load_categories()
    if cats:
        await update.message.reply_text(
            "Categories:\n" + "\n".join(f"• {c}" for c in cats))
    else:
        await update.message.reply_text("No categories yet.")


async def delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = " ".join(context.args).strip()
    if not name:
        await update.message.reply_text("Usage: /deletecategory <name>")
        return
    cats, removed = remove_category(name)
    remaining = ", ".join(cats) or "(none)"
    if removed:
        await update.message.reply_text(
            f"Deleted “{name}”. The bot will treat it as new again.\n"
            f"Remaining: {remaining}")
    else:
        await update.message.reply_text(
            f"No category matching “{name}”.\nCurrent: {remaining}")


async def _save_typed_category(update: Update, context: ContextTypes.DEFAULT_TYPE,
                               token: str) -> None:
    """Handle a free-text category name the user typed for a pending reel."""
    pipeline: Pipeline = context.application.bot_data["pipeline"]
    pending = context.application.bot_data.get("pending", {})
    entry = pending.pop(token, None)
    name = (update.message.text or "").strip()
    if entry is None:
        await update.message.reply_text("That request expired — send the reel again.")
        return
    if not name:
        await update.message.reply_text("A category name can't be empty — send the reel again.")
        return
    meta, tags, _proposed, title = entry
    category = match_category(name, load_categories()) or name
    try:
        if category == name:  # genuinely new name (no case-insensitive match)
            add_category(name)
        pipeline.save(meta, category, tags, title)
    except Exception as exc:  # noqa: BLE001 - surface save/Notion failures
        await update.message.reply_text(f"Couldn't save to Notion: {exc}")
        return
    await update.message.reply_text(f"Saved to {category}.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # If we previously asked this chat to type a category name, consume it here.
    token = context.chat_data.pop("awaiting_category_token", None)
    if token is not None:
        await _save_typed_category(update, context, token)
        return

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
                "✏️ Enter a different name", callback_data=f"type:{token}")])
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
    if action == "type":
        # Ask the user to type a name; keep the pending entry alive so the next
        # text message (handled in handle_message) can finish the save.
        context.chat_data["awaiting_category_token"] = token
        await query.edit_message_text(
            "✏️ Send me the category name you'd like to use for this reel."
        )
        return
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
    app.add_handler(CommandHandler("categories", list_categories))
    app.add_handler(CommandHandler("deletecategory", delete_category))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
