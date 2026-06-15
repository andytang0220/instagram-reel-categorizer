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
