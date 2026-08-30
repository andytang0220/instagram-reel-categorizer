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
