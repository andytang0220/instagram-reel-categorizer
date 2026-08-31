"""Fill in likes and thumbnails for reels saved before those were captured.

Run it manually:

    python -m reel_categorizer.backfill [--limit N] [--delay 3] [--force]

Every reel needs its own Instagram fetch, so this is deliberately slow and
polite. It is also safe to re-run: rows that already succeeded are skipped, so
an interrupted run just picks up where it left off. `--force` re-fetches
everything, which doubles as a way to refresh stale like counts.
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import load_settings, thumbnail_dir
from .fetchers import get_metadata
from .fetchers.apify_fetcher import ApifyFetcher
from .fetchers.ytdlp_fetcher import YtdlpFetcher
from .notion_store import NotionStore, ReelRow
from .thumbnails import cache_thumbnail, is_cached
from .urls import canonical_url

DEFAULT_DELAY = 3.0


@dataclass
class BackfillReport:
    updated: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def needs_backfill(row: ReelRow, thumb_root) -> bool:
    """True when this row is missing data a fetch could supply."""
    if not row.shortcode:
        return False  # nothing to fetch against
    return (row.likes is None
            or not row.thumbnail_url
            or not is_cached(row.shortcode, thumb_root))


def select_rows(rows, thumb_root, force: bool = False,
                limit: int | None = None) -> list[ReelRow]:
    selected = [r for r in rows
                if (r.shortcode if force else needs_backfill(r, thumb_root))]
    return selected[:limit] if limit else selected


def run_backfill(store, rows, fetch, cache_thumbnail, delay: float = 0.0,
                 sleep=time.sleep, log=lambda msg: None) -> BackfillReport:
    """Re-fetch each row and write likes + thumbnail back.

    Failures are collected rather than raised — a deleted or private reel
    should not abort a long run.
    """
    report = BackfillReport()
    for i, row in enumerate(rows):
        label = row.shortcode
        try:
            meta = fetch(row.url or canonical_url(row.shortcode), row.shortcode)
            store.update_entry(row.page_id, likes=meta.like_count,
                               thumbnail_url=meta.thumbnail_url)
            if meta.thumbnail_url:
                cache_thumbnail(row.shortcode, meta.thumbnail_url)
            report.updated.append(label)
            log(f"  [{i + 1}/{len(rows)}] {label}: "
                f"likes={meta.like_count} thumb={'yes' if meta.thumbnail_url else 'no'}")
        except Exception as exc:  # noqa: BLE001 - one bad reel must not stop the run
            report.failed.append((label, str(exc)))
            log(f"  [{i + 1}/{len(rows)}] {label}: FAILED - {exc}")
        if delay and i < len(rows) - 1:
            sleep(delay)
    return report


def main(argv=None) -> int:
    from notion_client import Client as NotionClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="only process the first N reels")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help="seconds to wait between reels (default: 3)")
    parser.add_argument("--force", action="store_true",
                        help="re-fetch every reel, refreshing like counts")
    args = parser.parse_args(argv)

    settings = load_settings()
    store = NotionStore(
        NotionClient(auth=settings.notion_token), settings.notion_database_id)
    fetchers = [YtdlpFetcher(), ApifyFetcher(settings.apify_token)]
    root = Path(thumbnail_dir())
    root.mkdir(parents=True, exist_ok=True)

    print("Reading the database...")
    rows = store.query_all()
    selected = select_rows(rows, root, force=args.force, limit=args.limit)
    print(f"{len(rows)} reels total, {len(selected)} to process.\n")
    if not selected:
        print("Nothing to do.")
        return 0

    report = run_backfill(
        store, selected,
        fetch=lambda url, sc: get_metadata(url, sc, fetchers),
        cache_thumbnail=lambda sc, url: cache_thumbnail(sc, url, root),
        delay=args.delay, log=print,
    )

    print(f"\nUpdated {len(report.updated)}, failed {len(report.failed)}.")
    for shortcode, err in report.failed:
        print(f"  {shortcode}: {err}")
    if report.failed:
        print("\nRe-run to retry the failures (successes are skipped).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
