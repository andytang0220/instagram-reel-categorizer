from reel_categorizer.backfill import (
    needs_backfill, run_backfill, select_rows)
from reel_categorizer.fetchers.base import FetchError
from reel_categorizer.models import ReelMetadata
from reel_categorizer.notion_store import ReelRow


def _row(shortcode="abc", likes=1, thumbnail_url="https://cdn/t.jpg"):
    return ReelRow(page_id=f"page-{shortcode}", shortcode=shortcode,
                   url=f"https://www.instagram.com/reel/{shortcode}/",
                   likes=likes, thumbnail_url=thumbnail_url)


def _cached(tmp_path, shortcode="abc"):
    (tmp_path / f"{shortcode}.jpg").write_bytes(b"\xff\xd8jpeg")
    return tmp_path


# --- needs_backfill --------------------------------------------------------

def test_complete_row_needs_nothing(tmp_path):
    assert needs_backfill(_row(), _cached(tmp_path)) is False


def test_row_without_likes_needs_backfill(tmp_path):
    assert needs_backfill(_row(likes=None), _cached(tmp_path)) is True


def test_zero_likes_is_complete(tmp_path):
    """0 likes is a real answer, not a missing one."""
    assert needs_backfill(_row(likes=0), _cached(tmp_path)) is False


def test_row_without_thumbnail_url_needs_backfill(tmp_path):
    assert needs_backfill(_row(thumbnail_url=""), _cached(tmp_path)) is True


def test_row_with_uncached_image_needs_backfill(tmp_path):
    assert needs_backfill(_row(), tmp_path) is True


def test_row_without_shortcode_is_unfixable(tmp_path):
    """Nothing to fetch, so never select it."""
    row = ReelRow(page_id="p", shortcode="", url="", likes=None)
    assert needs_backfill(row, tmp_path) is False


# --- select_rows -----------------------------------------------------------

def test_select_rows_picks_only_incomplete_rows(tmp_path):
    _cached(tmp_path, "done")
    rows = [_row("done"), _row("nothumb", thumbnail_url="")]
    assert [r.shortcode for r in select_rows(rows, tmp_path)] == ["nothumb"]


def test_select_rows_force_takes_everything_fixable(tmp_path):
    _cached(tmp_path, "done")
    rows = [_row("done"), ReelRow(page_id="p", shortcode="")]
    assert [r.shortcode for r in select_rows(rows, tmp_path, force=True)] == ["done"]


def test_select_rows_honours_limit(tmp_path):
    rows = [_row("a"), _row("b"), _row("c")]
    assert len(select_rows(rows, tmp_path, limit=2)) == 2


# --- run_backfill ----------------------------------------------------------

class _Store:
    def __init__(self):
        self.updated = []

    def update_entry(self, page_id, likes=None, thumbnail_url=None):
        self.updated.append((page_id, likes, thumbnail_url))


def _fetch_ok(url, shortcode):
    return ReelMetadata(shortcode=shortcode, url=url,
                        thumbnail_url="https://cdn/fresh.jpg", like_count=999)


def test_run_backfill_updates_notion_and_caches_thumbnail(tmp_path):
    store, cached = _Store(), []
    report = run_backfill(
        store, [_row("abc", likes=None)], fetch=_fetch_ok,
        cache_thumbnail=lambda s, u: cached.append((s, u)), sleep=lambda s: None)
    assert store.updated == [("page-abc", 999, "https://cdn/fresh.jpg")]
    assert cached == [("abc", "https://cdn/fresh.jpg")]
    assert report.updated == ["abc"]
    assert report.failed == []


def test_run_backfill_records_fetch_failures_without_stopping(tmp_path):
    """A deleted or private reel must not abort the rest of the run."""
    def fetch(url, shortcode):
        if shortcode == "gone":
            raise FetchError("404")
        return _fetch_ok(url, shortcode)

    store = _Store()
    report = run_backfill(
        store, [_row("gone"), _row("fine")], fetch=fetch,
        cache_thumbnail=lambda s, u: None, sleep=lambda s: None)
    assert report.updated == ["fine"]
    assert [sc for sc, _ in report.failed] == ["gone"]
    assert [p for p, _, _ in store.updated] == ["page-fine"]


def test_run_backfill_records_notion_write_failures():
    class _Boom(_Store):
        def update_entry(self, page_id, likes=None, thumbnail_url=None):
            raise RuntimeError("notion down")

    report = run_backfill(
        _Boom(), [_row("abc")], fetch=_fetch_ok,
        cache_thumbnail=lambda s, u: None, sleep=lambda s: None)
    assert report.updated == []
    assert report.failed[0][0] == "abc"


def test_run_backfill_sleeps_between_reels_but_not_after_the_last():
    slept = []
    run_backfill(
        _Store(), [_row("a"), _row("b")], fetch=_fetch_ok,
        cache_thumbnail=lambda s, u: None, delay=3, sleep=slept.append)
    assert slept == [3]


def test_run_backfill_on_an_empty_selection_does_nothing():
    report = run_backfill(_Store(), [], fetch=_fetch_ok,
                          cache_thumbnail=lambda s, u: None, sleep=lambda s: None)
    assert report.updated == []
    assert report.failed == []
