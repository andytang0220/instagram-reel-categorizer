from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ReelMetadata:
    """Normalized reel metadata returned by every fetcher."""

    shortcode: str
    url: str
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    author: str = ""
    post_date: date | None = None
    source: str = ""
