import pytest

from reel_categorizer.thumbnails import (
    MAX_THUMBNAIL_BYTES, cache_thumbnail, thumb_path)

_JPEG = b"\xff\xd8\xff\xe0" + b"x" * 100


class _Resp:
    def __init__(self, content=_JPEG, content_type="image/jpeg", boom=False):
        self.content = content
        self.headers = {"Content-Type": content_type}
        self._boom = boom

    def raise_for_status(self):
        if self._boom:
            raise RuntimeError("404")


class _Http:
    def __init__(self, resp=None, raises=None):
        self._resp = resp if resp is not None else _Resp()
        self._raises = raises
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        if self._raises:
            raise self._raises
        return self._resp


def test_thumb_path_is_shortcode_jpg_under_root(tmp_path):
    assert thumb_path("aBc-1_2", tmp_path) == tmp_path / "aBc-1_2.jpg"


def test_cache_thumbnail_writes_file_and_returns_path(tmp_path):
    http = _Http()
    path = cache_thumbnail("abc", "https://cdn/t.jpg", tmp_path, http=http)
    assert path == tmp_path / "abc.jpg"
    assert path.read_bytes() == _JPEG
    assert http.calls[0][0] == "https://cdn/t.jpg"


def test_cache_thumbnail_creates_root_directory(tmp_path):
    root = tmp_path / "nested" / "thumbs"
    assert cache_thumbnail("abc", "https://cdn/t.jpg", root, http=_Http()) is not None
    assert (root / "abc.jpg").exists()


def test_cache_thumbnail_skips_download_when_already_cached(tmp_path):
    (tmp_path / "abc.jpg").write_bytes(b"old")
    http = _Http()
    path = cache_thumbnail("abc", "https://cdn/t.jpg", tmp_path, http=http)
    assert path == tmp_path / "abc.jpg"
    assert path.read_bytes() == b"old"
    assert http.calls == []


def test_cache_thumbnail_without_url_returns_none(tmp_path):
    assert cache_thumbnail("abc", "", tmp_path, http=_Http()) is None
    assert cache_thumbnail("abc", None, tmp_path, http=_Http()) is None


def test_cache_thumbnail_rejects_non_image_content_type(tmp_path):
    http = _Http(_Resp(content=b"<html>nope</html>", content_type="text/html"))
    assert cache_thumbnail("abc", "https://cdn/t.jpg", tmp_path, http=http) is None
    assert not (tmp_path / "abc.jpg").exists()


def test_cache_thumbnail_rejects_oversized_body(tmp_path):
    http = _Http(_Resp(content=b"x" * (MAX_THUMBNAIL_BYTES + 1)))
    assert cache_thumbnail("abc", "https://cdn/t.jpg", tmp_path, http=http) is None
    assert not (tmp_path / "abc.jpg").exists()


def test_cache_thumbnail_rejects_empty_body(tmp_path):
    http = _Http(_Resp(content=b""))
    assert cache_thumbnail("abc", "https://cdn/t.jpg", tmp_path, http=http) is None
    assert not (tmp_path / "abc.jpg").exists()


def test_cache_thumbnail_returns_none_on_http_error(tmp_path):
    http = _Http(raises=RuntimeError("connection reset"))
    assert cache_thumbnail("abc", "https://cdn/t.jpg", tmp_path, http=http) is None


def test_cache_thumbnail_returns_none_on_bad_status(tmp_path):
    http = _Http(_Resp(boom=True))
    assert cache_thumbnail("abc", "https://cdn/t.jpg", tmp_path, http=http) is None


@pytest.mark.parametrize("shortcode", ["", "../evil", "a/b", "a\\b", "."])
def test_cache_thumbnail_rejects_unsafe_shortcodes(tmp_path, shortcode):
    assert cache_thumbnail(shortcode, "https://cdn/t.jpg", tmp_path,
                           http=_Http()) is None


def test_cache_thumbnail_leaves_no_partial_file_on_failure(tmp_path):
    """A rejected download must not leave a .tmp sibling behind."""
    http = _Http(_Resp(content=b"nope", content_type="text/html"))
    cache_thumbnail("abc", "https://cdn/t.jpg", tmp_path, http=http)
    assert list(tmp_path.iterdir()) == []
