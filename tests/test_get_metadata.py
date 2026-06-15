import pytest

from reel_categorizer.fetchers import get_metadata
from reel_categorizer.fetchers.base import MetadataFetcher, FetchError
from reel_categorizer.models import ReelMetadata


class _OK(MetadataFetcher):
    name = "ok"

    def fetch(self, url, shortcode):
        return ReelMetadata(shortcode=shortcode, url=url, source="ok")


class _Fail(MetadataFetcher):
    name = "fail"

    def fetch(self, url, shortcode):
        raise FetchError("nope")


def test_returns_first_success():
    assert get_metadata("u", "abc", [_OK()]).source == "ok"


def test_falls_back_on_failure():
    assert get_metadata("u", "abc", [_Fail(), _OK()]).source == "ok"


def test_all_fail_raises():
    with pytest.raises(FetchError):
        get_metadata("u", "abc", [_Fail(), _Fail()])
