from __future__ import annotations

import re

_SHORTCODE_RE = re.compile(r"instagram\.com/(?:reel|reels|p)/([A-Za-z0-9_-]+)")


class InvalidReelURL(ValueError):
    """Raised when a URL is not a recognizable Instagram reel/post link."""


def extract_shortcode(url: str) -> str:
    match = _SHORTCODE_RE.search(url or "")
    if not match:
        raise InvalidReelURL(f"Not a recognized Instagram reel URL: {url!r}")
    return match.group(1)


def canonical_url(shortcode: str) -> str:
    return f"https://www.instagram.com/reel/{shortcode}/"
