from __future__ import annotations

from dataclasses import dataclass, field

from .classifier import Classification
from .fetchers import get_metadata
from .fetchers.base import FetchError
from .models import ReelMetadata
from .urls import InvalidReelURL, canonical_url, extract_shortcode


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
    def __init__(self, fetchers, classifier, store, load_categories):
        self.fetchers = fetchers
        self.classifier = classifier
        self.store = store
        self.load_categories = load_categories

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
        return ProcessResult(
            "saved", f"Saved to {result.category}.",
            category=result.category, tags=result.tags, meta=meta,
            title=result.title,
        )

    def save(
        self, meta: ReelMetadata, category: str, tags: list[str],
        title: str = "",
    ) -> str:
        return self.store.create_entry(meta, category, tags, title)
