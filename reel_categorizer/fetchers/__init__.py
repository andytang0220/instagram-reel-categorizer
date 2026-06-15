from __future__ import annotations

from ..models import ReelMetadata
from .base import FetchError, MetadataFetcher


def get_metadata(
    url: str, shortcode: str, fetchers: list[MetadataFetcher]
) -> ReelMetadata:
    errors = []
    for fetcher in fetchers:
        try:
            return fetcher.fetch(url, shortcode)
        except FetchError as exc:
            errors.append(f"{fetcher.name}: {exc}")
    raise FetchError("All fetchers failed -> " + " | ".join(errors))
