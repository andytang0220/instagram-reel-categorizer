from __future__ import annotations

from dataclasses import dataclass, field

from .classifier import Classification
from .config import thumbnail_dir
from .fetchers import get_metadata
from .fetchers.base import FetchError
from .models import ReelMetadata
from .thumbnails import cache_thumbnail as _cache_thumbnail
from .urls import InvalidReelURL, canonical_url, extract_shortcode


def _default_cacher(shortcode: str, url: str):
    return _cache_thumbnail(shortcode, url, thumbnail_dir())


@dataclass
class ProcessResult:
    kind: str  # invalid | duplicate | error | needs_category | saved
    message: str
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    proposed_category: str | None = None
    meta: ReelMetadata | None = None
    title: str = ""


class Pipeline:
    def __init__(self, fetchers, classifier, store, load_categories,
                 cache_thumbnail=None):
        self.fetchers = fetchers
        self.classifier = classifier
        self.store = store
        self.load_categories = load_categories
        # cache_thumbnail(shortcode, url) -> path | None
        self.cache_thumbnail = cache_thumbnail or _default_cacher

    def _cache_thumbnail(self, meta: ReelMetadata) -> None:
        """Best-effort thumbnail download. A failure never fails the save."""
        if not meta.thumbnail_url:
            return
        try:
            self.cache_thumbnail(meta.shortcode, meta.thumbnail_url)
        except Exception:  # noqa: BLE001 - the reel is already saved
            pass

    def process(self, url: str) -> ProcessResult:
        try:
            shortcode = extract_shortcode(url)
        except InvalidReelURL:
            return ProcessResult(
                "invalid", "That doesn't look like an Instagram reel link."
            )

        existing = self.store.find_by_shortcode(shortcode)
        if existing:
            return ProcessResult(
                "duplicate", f"Already saved under {existing}.", category=existing
            )

        try:
            meta = get_metadata(canonical_url(shortcode), shortcode, self.fetchers)
        except FetchError as exc:
            return ProcessResult("error", f"Couldn't fetch that reel ({exc}).")

        categories = self.load_categories()
        try:
            existing_tags = self.store.existing_tags()
            result = self.classifier.classify(meta, categories, existing_tags)
        except Exception as exc:  # noqa: BLE001 - surface any classify failure
            return ProcessResult("error", f"Classification failed ({exc}).")

        if result.is_new_category or result.category not in categories:
            return ProcessResult(
                "needs_category",
                f"No existing category fits — I'd suggest “{result.category}”.",
                proposed_category=result.category,
                tags=result.tags,
                meta=meta,
                title=result.title,
            )

        try:
            self.store.create_entry(meta, result.category, result.tags, result.title)
        except Exception as exc:  # noqa: BLE001 - surface any Notion write failure
            return ProcessResult("error", f"Couldn't save to Notion ({exc}).")
        self._cache_thumbnail(meta)
        return ProcessResult(
            "saved", f"Saved to {result.category}.",
            category=result.category, tags=result.tags, meta=meta,
            title=result.title,
        )

    def save(
        self, meta: ReelMetadata, category: str, tags: list[str],
        title: str = "",
    ) -> str:
        url = self.store.create_entry(meta, category, tags, title)
        self._cache_thumbnail(meta)
        return url
