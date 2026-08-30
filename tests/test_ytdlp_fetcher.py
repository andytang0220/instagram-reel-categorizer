from datetime import date

import pytest

from reel_categorizer.fetchers.ytdlp_fetcher import YtdlpFetcher
from reel_categorizer.fetchers.base import FetchError


class _FakeYDL:
    def __init__(self, info):
        self._info = info

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        return self._info


def test_ytdlp_normalizes_info():
    info = {"description": "Best tacos #food #tacos",
            "uploader": "chef", "upload_date": "20260110"}
    f = YtdlpFetcher(ydl_factory=lambda: _FakeYDL(info))
    m = f.fetch("https://www.instagram.com/reel/abc/", "abc")
    assert m.caption == "Best tacos #food #tacos"
    assert m.hashtags == ["food", "tacos"]
    assert m.author == "chef"
    assert m.post_date == date(2026, 1, 10)
    assert m.source == "ytdlp"


def test_ytdlp_handles_missing_fields():
    f = YtdlpFetcher(ydl_factory=lambda: _FakeYDL({}))
    m = f.fetch("https://www.instagram.com/reel/abc/", "abc")
    assert m.caption == ""
    assert m.author == ""
    assert m.post_date is None


def test_ytdlp_raises_fetcherror():
    class _Boom:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, *a, **k):
            raise RuntimeError("blocked")

    f = YtdlpFetcher(ydl_factory=lambda: _Boom())
    with pytest.raises(FetchError):
        f.fetch("u", "abc")


def test_ytdlp_version_supports_current_instagram():
    """Instagram gates anonymous metadata; older extractors get HTTP 401.

    yt-dlp 2026.06.09 and earlier fail every anonymous path for reels
    (GraphQL -> 401 require_login, page/embed -> bare JS shell with no
    metadata), which pushes every fetch onto the paid Apify fallback.
    2026.08.19 uses a working path. Instagram breaks scrapers often, so
    this pins the floor to a version verified against a live reel.
    """
    from importlib.metadata import version

    installed = tuple(int(p) for p in version("yt-dlp").split(".")[:3])
    assert installed >= (2026, 8, 19), (
        f"yt-dlp {version('yt-dlp')} is too old for Instagram's current "
        "anonymous-access rules; upgrade it"
    )


def test_ytdlp_extracts_thumbnail_and_view_count():
    info = {"description": "hi", "thumbnail": "https://cdn/t.jpg",
            "view_count": 98765}
    f = YtdlpFetcher(ydl_factory=lambda: _FakeYDL(info))
    m = f.fetch("https://www.instagram.com/reel/abc/", "abc")
    assert m.thumbnail_url == "https://cdn/t.jpg"
    assert m.view_count == 98765


def test_ytdlp_falls_back_to_largest_thumbnails_entry():
    """`thumbnail` is sometimes absent while `thumbnails` is populated."""
    info = {"thumbnails": [
        {"url": "https://cdn/small.jpg", "width": 150},
        {"url": "https://cdn/big.jpg", "width": 1080},
        {"url": "https://cdn/mid.jpg", "width": 640},
    ]}
    f = YtdlpFetcher(ydl_factory=lambda: _FakeYDL(info))
    m = f.fetch("u", "abc")
    assert m.thumbnail_url == "https://cdn/big.jpg"


def test_ytdlp_thumbnails_without_width_uses_last_entry():
    info = {"thumbnails": [{"url": "https://cdn/a.jpg"}, {"url": "https://cdn/b.jpg"}]}
    f = YtdlpFetcher(ydl_factory=lambda: _FakeYDL(info))
    assert f.fetch("u", "abc").thumbnail_url == "https://cdn/b.jpg"


def test_ytdlp_missing_thumbnail_and_views_stay_empty():
    f = YtdlpFetcher(ydl_factory=lambda: _FakeYDL({}))
    m = f.fetch("u", "abc")
    assert m.thumbnail_url == ""
    assert m.view_count is None


def test_ytdlp_non_numeric_view_count_is_none():
    f = YtdlpFetcher(ydl_factory=lambda: _FakeYDL({"view_count": "lots"}))
    assert f.fetch("u", "abc").view_count is None
