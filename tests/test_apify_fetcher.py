from datetime import date

import pytest

from reel_categorizer.fetchers.apify_fetcher import ApifyFetcher
from reel_categorizer.fetchers.base import FetchError


class _Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _Http:
    def __init__(self, data):
        self._data = data
        self.calls = []

    def post(self, url, json=None):
        self.calls.append((url, json))
        return _Resp(self._data)


def test_apify_disabled_without_token():
    f = ApifyFetcher(token=None)
    with pytest.raises(FetchError):
        f.fetch("u", "abc")


def test_apify_normalizes_item():
    item = {"caption": "Gym day #fitness", "ownerUsername": "fit",
            "hashtags": ["Fitness"], "timestamp": "2026-02-03T10:00:00.000Z"}
    http = _Http([item])
    f = ApifyFetcher(token="tok", http=http)
    m = f.fetch("https://www.instagram.com/reel/abc/", "abc")
    assert m.author == "fit"
    assert m.hashtags == ["fitness"]
    assert m.post_date == date(2026, 2, 3)
    assert m.source == "apify"
    assert "tok" in http.calls[0][0]


def test_apify_empty_raises():
    f = ApifyFetcher(token="tok", http=_Http([]))
    with pytest.raises(FetchError):
        f.fetch("u", "abc")


def test_apify_extracts_thumbnail_and_like_count():
    item = {"caption": "hi", "displayUrl": "https://cdn/d.jpg",
            "likesCount": 4321}
    f = ApifyFetcher(token="tok", http=_Http([item]))
    m = f.fetch("u", "abc")
    assert m.thumbnail_url == "https://cdn/d.jpg"
    assert m.like_count == 4321


def test_apify_negative_like_count_is_none():
    """The actor reports -1 when likes are hidden on the post."""
    f = ApifyFetcher(token="tok", http=_Http([{"likesCount": -1}]))
    assert f.fetch("u", "abc").like_count is None


def test_apify_missing_thumbnail_and_likes_stay_empty():
    f = ApifyFetcher(token="tok", http=_Http([{"caption": "hi"}]))
    m = f.fetch("u", "abc")
    assert m.thumbnail_url == ""
    assert m.like_count is None
