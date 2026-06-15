from __future__ import annotations

from datetime import datetime

import requests

from ..models import ReelMetadata
from .base import FetchError, MetadataFetcher, parse_hashtags

APIFY_ACTOR = "apify~instagram-scraper"


class ApifyFetcher(MetadataFetcher):
    name = "apify"

    def __init__(self, token: str | None, http=requests):
        self._token = token
        self._http = http

    def fetch(self, url: str, shortcode: str) -> ReelMetadata:
        if not self._token:
            raise FetchError("Apify token not configured")
        endpoint = (
            f"https://api.apify.com/v2/acts/{APIFY_ACTOR}"
            f"/run-sync-get-dataset-items?token={self._token}"
        )
        try:
            resp = self._http.post(
                endpoint, json={"directUrls": [url], "resultsLimit": 1}
            )
            resp.raise_for_status()
            items = resp.json()
        except Exception as exc:
            raise FetchError(f"Apify request failed: {exc}") from exc
        if not items:
            raise FetchError("Apify returned no items")
        return self._normalize(items[0], url, shortcode)

    def _normalize(self, item: dict, url: str, shortcode: str) -> ReelMetadata:
        caption = item.get("caption") or ""
        hashtags = [h.lower() for h in item.get("hashtags", [])]
        if not hashtags:
            hashtags = parse_hashtags(caption)
        post_date = None
        ts = item.get("timestamp")
        if isinstance(ts, str):
            try:
                post_date = datetime.fromisoformat(
                    ts.replace("Z", "+00:00")
                ).date()
            except ValueError:
                post_date = None
        return ReelMetadata(
            shortcode=shortcode,
            url=url,
            caption=caption,
            hashtags=hashtags,
            author=item.get("ownerUsername") or "",
            post_date=post_date,
            source=self.name,
        )
