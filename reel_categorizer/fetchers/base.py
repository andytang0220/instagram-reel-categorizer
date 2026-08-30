from __future__ import annotations

import re
from abc import ABC, abstractmethod

from ..models import ReelMetadata

_HASHTAG_RE = re.compile(r"#(\w+)")


def parse_hashtags(caption: str | None) -> list[str]:
    return [h.lower() for h in _HASHTAG_RE.findall(caption or "")]


def to_int(value) -> int | None:
    """Coerce a view count to int, or None when it isn't a usable number.

    Fetchers report counts inconsistently (missing, null, or occasionally a
    string), and a missing count must never break a fetch.
    """
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class FetchError(Exception):
    """Raised when a fetcher cannot retrieve reel metadata."""


class MetadataFetcher(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, url: str, shortcode: str) -> ReelMetadata:
        ...
