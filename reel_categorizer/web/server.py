"""Local web server backing the reel browser.

The Notion token has to stay server-side, so the browser talks to this app
instead of Notion directly. It exposes the saved reels as JSON and serves the
locally cached thumbnails, plus the built frontend when one exists.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..config import load_categories, load_settings, thumbnail_dir
from ..notion_store import NotionStore
from ..thumbnails import cache_thumbnail as _cache_thumbnail
from ..thumbnails import is_safe_shortcode, thumb_path

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _ordered_categories(configured: list[str], rows) -> list[str]:
    """Configured categories first, then any others still present on rows.

    A category removed from categories.json keeps its saved reels visible
    instead of silently hiding them.
    """
    seen = list(configured)
    for row in rows:
        if row.category and row.category not in seen:
            seen.append(row.category)
    return seen


def create_app(store, categories_loader, thumb_root, cache_thumbnail=None,
               frontend_dist=FRONTEND_DIST) -> FastAPI:
    app = FastAPI(title="Reel Browser")
    root = Path(thumb_root)
    cacher = cache_thumbnail or (
        lambda shortcode, url: _cache_thumbnail(shortcode, url, root))

    # shortcode -> CDN URL, refreshed on every /api/reels call. Lets a thumbnail
    # cache miss retry the original URL without a second Notion round trip.
    thumb_urls: dict[str, str] = {}

    @app.get("/api/reels")
    def reels():
        try:
            rows = store.query_all()
        except Exception as exc:  # noqa: BLE001 - surface Notion failures as 502
            raise HTTPException(502, f"Couldn't read from Notion: {exc}") from exc
        thumb_urls.clear()
        thumb_urls.update(
            {r.shortcode: r.thumbnail_url for r in rows
             if r.shortcode and r.thumbnail_url})
        return {
            "categories": _ordered_categories(categories_loader(), rows),
            "reels": [asdict(r) for r in rows],
        }

    @app.get("/thumbs/{shortcode}.jpg")
    def thumb(shortcode: str):
        if not is_safe_shortcode(shortcode):
            raise HTTPException(400, "Bad shortcode")
        path = thumb_path(shortcode, root)
        if not path.is_file():
            # The image was never cached (an old row, or the bot's download
            # failed). Try the stored CDN URL once; it may still be live.
            url = thumb_urls.get(shortcode)
            if not url or not cacher(shortcode, url) or not path.is_file():
                raise HTTPException(404, "No thumbnail")
        return FileResponse(path, media_type="image/jpeg")

    if Path(frontend_dist).is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True),
                  name="frontend")

    return app


def build_app() -> FastAPI:
    from notion_client import Client as NotionClient

    settings = load_settings()
    store = NotionStore(
        NotionClient(auth=settings.notion_token), settings.notion_database_id)
    return create_app(store, load_categories, thumbnail_dir())
