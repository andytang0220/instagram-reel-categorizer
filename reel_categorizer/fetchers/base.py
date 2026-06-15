from __future__ import annotations

import re
from abc import ABC, abstractmethod

from ..models import ReelMetadata

_HASHTAG_RE = re.compile(r"#(\w+)")


def parse_hashtags(caption: str | None) -> list[str]:
    return [h.lower() for h in _HASHTAG_RE.findall(caption or "")]


class FetchError(Exception):
    """Raised when a fetcher cannot retrieve reel metadata."""


class MetadataFetcher(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, url: str, shortcode: str) -> ReelMetadata:
        ...
