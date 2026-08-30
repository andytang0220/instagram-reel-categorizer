from __future__ import annotations

from datetime import datetime

import yt_dlp

from ..models import ReelMetadata
from .base import FetchError, MetadataFetcher, parse_hashtags, to_int


def _pick_thumbnail(info: dict) -> str:
    """Best available thumbnail URL from a yt-dlp info dict.

    Prefers the flat `thumbnail` key; falls back to the widest entry in
    `thumbnails`, which is what the reel extractor populates when it can't
    single out a primary image.
    """
    if info.get("thumbnail"):
        return str(info["thumbnail"])
    candidates = [t for t in info.get("thumbnails") or [] if t.get("url")]
    if not candidates:
        return ""
    widest = max(
        enumerate(candidates),
        key=lambda pair: (to_int(pair[1].get("width")) or 0, pair[0]),
    )[1]
    return str(widest["url"])


def _default_factory():
    return yt_dlp.YoutubeDL(
        {"quiet": True, "skip_download": True, "no_warnings": True}
    )


class YtdlpFetcher(MetadataFetcher):
    name = "ytdlp"

    def __init__(self, ydl_factory=None):
        self._ydl_factory = ydl_factory or _default_factory

    def fetch(self, url: str, shortcode: str) -> ReelMetadata:
        try:
            with self._ydl_factory() as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:  # yt-dlp raises many error types
            raise FetchError(f"yt-dlp failed: {exc}") from exc
        return self._normalize(info or {}, url, shortcode)

    def _normalize(self, info: dict, url: str, shortcode: str) -> ReelMetadata:
        caption = info.get("description") or ""
        post_date = None
        if info.get("timestamp"):
            post_date = datetime.utcfromtimestamp(info["timestamp"]).date()
        elif info.get("upload_date"):
            post_date = datetime.strptime(info["upload_date"], "%Y%m%d").date()
        return ReelMetadata(
            shortcode=shortcode,
            url=url,
            caption=caption,
            hashtags=parse_hashtags(caption),
            author=info.get("uploader") or info.get("uploader_id") or "",
            post_date=post_date,
            source=self.name,
            thumbnail_url=_pick_thumbnail(info),
            view_count=to_int(info.get("view_count")),
        )
