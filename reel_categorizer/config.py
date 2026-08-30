from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_CATEGORIES_PATH = Path(os.getenv("CATEGORIES_PATH", "categories.json"))


def thumbnail_dir() -> Path:
    """Where downloaded reel thumbnails are cached."""
    return Path(os.getenv("THUMBNAIL_DIR", "thumbnails"))


def load_categories(path: Path = DEFAULT_CATEGORIES_PATH) -> list[str]:
    return json.loads(Path(path).read_text())


def add_category(name: str, path: Path = DEFAULT_CATEGORIES_PATH) -> list[str]:
    path = Path(path)
    cats = load_categories(path)
    if name not in cats:
        cats.append(name)
        path.write_text(json.dumps(cats, indent=2))
    return cats


def remove_category(
    name: str, path: Path = DEFAULT_CATEGORIES_PATH
) -> tuple[list[str], bool]:
    """Remove a category (case-insensitive) from the list file.

    Returns (updated categories, removed?). A no-op (returns removed=False) when
    no category matches. Only touches `categories.json` — Notion's existing rows
    and select options are left alone, so removing a category simply makes the
    bot treat it as new again next time.
    """
    path = Path(path)
    cats = load_categories(path)
    canonical = match_category(name, cats)
    if canonical is None:
        return cats, False
    cats = [c for c in cats if c != canonical]
    path.write_text(json.dumps(cats, indent=2))
    return cats, True


def match_category(name: str, categories: list[str]) -> str | None:
    """Return the existing category matching `name` case-insensitively, else None.

    Lets a user-typed category name reuse an existing category's canonical
    spelling instead of creating a near-duplicate (e.g. "tech" -> "Tech").
    """
    n = name.strip().lower()
    if not n:
        return None
    for c in categories:
        if c.lower() == n:
            return c
    return None


@dataclass
class Settings:
    telegram_token: str
    anthropic_api_key: str
    notion_token: str
    notion_database_id: str
    apify_token: str | None = None


def load_settings(env: dict | None = None) -> Settings:
    env = env if env is not None else os.environ
    return Settings(
        telegram_token=env["TELEGRAM_BOT_TOKEN"],
        anthropic_api_key=env["ANTHROPIC_API_KEY"],
        notion_token=env["NOTION_TOKEN"],
        notion_database_id=env["NOTION_DATABASE_ID"],
        apify_token=env.get("APIFY_TOKEN") or None,
    )
