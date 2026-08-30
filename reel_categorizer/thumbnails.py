"""Local disk cache for reel thumbnails.

Instagram's CDN URLs are signed and expire within days or weeks, so the image
bytes are downloaded once at save time and served from here afterwards.

Every function here is best-effort: a thumbnail is a nicety, and no failure
should ever propagate into the save path.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import requests

MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024
DOWNLOAD_TIMEOUT = 15

# Matches Instagram shortcodes; also keeps a hostile value from escaping the
# cache directory, since the shortcode becomes a filename.
_SAFE_SHORTCODE = re.compile(r"^[A-Za-z0-9_-]+$")


def is_safe_shortcode(shortcode: str) -> bool:
    return bool(shortcode) and bool(_SAFE_SHORTCODE.match(shortcode))


def thumb_path(shortcode: str, root) -> Path:
    return Path(root) / f"{shortcode}.jpg"


def is_cached(shortcode: str, root) -> bool:
    return is_safe_shortcode(shortcode) and thumb_path(shortcode, root).is_file()


def cache_thumbnail(shortcode: str, url: str | None, root, http=requests):
    """Download `url` into the cache as `<shortcode>.jpg`.

    Returns the cached path, or None if there was nothing to fetch or the
    fetch failed. Already-cached files are returned untouched, so this is
    cheap to call repeatedly and safe to re-run.
    """
    if not is_safe_shortcode(shortcode) or not url:
        return None

    path = thumb_path(shortcode, root)
    if path.is_file():
        return path

    try:
        resp = http.get(url, timeout=DOWNLOAD_TIMEOUT)
        resp.raise_for_status()
        content_type = (resp.headers or {}).get("Content-Type", "")
        if not content_type.lower().startswith("image/"):
            return None
        body = resp.content
        if not body or len(body) > MAX_THUMBNAIL_BYTES:
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write then rename so a partial download is never served.
        tmp = path.with_suffix(".jpg.tmp")
        tmp.write_bytes(body)
        os.replace(tmp, path)
        return path
    except Exception:  # noqa: BLE001 - a missing thumbnail is never fatal
        return None
