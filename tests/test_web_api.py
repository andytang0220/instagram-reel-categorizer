import pytest
from fastapi.testclient import TestClient

from reel_categorizer.notion_store import ReelRow
from reel_categorizer.web.server import create_app

_JPEG = b"\xff\xd8\xff\xe0" + b"x" * 20


def _row(shortcode, category="Tech", views=None, tags=None, added="2026-01-01",
         thumbnail_url=""):
    return ReelRow(
        page_id=f"page-{shortcode}", shortcode=shortcode,
        title=f"chef - {shortcode}", url=f"https://instagram.com/reel/{shortcode}/",
        category=category, tags=list(tags or []), author="chef", views=views,
        post_date="2025-12-01", date_added=added, thumbnail_url=thumbnail_url,
    )


class _Store:
    def __init__(self, rows=None, raises=None):
        self._rows = list(rows or [])
        self._raises = raises
        self.query_count = 0

    def query_all(self):
        self.query_count += 1
        if self._raises:
            raise self._raises
        return self._rows


def _client(store=None, categories=("Tech", "Fitness"), tmp_path=None,
            cacher=None):
    app = create_app(
        store=store if store is not None else _Store(),
        categories_loader=lambda: list(categories),
        thumb_root=tmp_path,
        cache_thumbnail=cacher or (lambda shortcode, url: None),
    )
    return TestClient(app)


# --- /api/reels ------------------------------------------------------------

def test_reels_returns_categories_and_rows(tmp_path):
    store = _Store([_row("a", "Tech", views=10, tags=["ai"])])
    body = _client(store, tmp_path=tmp_path).get("/api/reels").json()
    assert body["categories"] == ["Tech", "Fitness"]
    assert len(body["reels"]) == 1
    reel = body["reels"][0]
    assert reel["shortcode"] == "a"
    assert reel["category"] == "Tech"
    assert reel["views"] == 10
    assert reel["tags"] == ["ai"]
    assert reel["url"] == "https://instagram.com/reel/a/"
    assert reel["title"] == "chef - a"


def test_reels_preserves_store_ordering(tmp_path):
    """query_all already sorts newest-first; the API must not reshuffle."""
    store = _Store([_row("new", added="2026-05-01"),
                    _row("old", added="2024-01-01")])
    body = _client(store, tmp_path=tmp_path).get("/api/reels").json()
    assert [r["shortcode"] for r in body["reels"]] == ["new", "old"]


def test_reels_appends_categories_present_only_in_rows(tmp_path):
    """A category deleted from categories.json still shows its saved reels."""
    store = _Store([_row("a", "Retired Category")])
    body = _client(store, tmp_path=tmp_path).get("/api/reels").json()
    assert body["categories"] == ["Tech", "Fitness", "Retired Category"]


def test_reels_ignores_rows_with_no_category(tmp_path):
    store = _Store([_row("a", category="")])
    body = _client(store, tmp_path=tmp_path).get("/api/reels").json()
    assert body["categories"] == ["Tech", "Fitness"]


def test_reels_does_not_duplicate_categories(tmp_path):
    store = _Store([_row("a", "Tech"), _row("b", "Tech")])
    body = _client(store, tmp_path=tmp_path).get("/api/reels").json()
    assert body["categories"] == ["Tech", "Fitness"]


def test_reels_reports_notion_failure_as_502(tmp_path):
    store = _Store(raises=RuntimeError("notion down"))
    resp = _client(store, tmp_path=tmp_path).get("/api/reels")
    assert resp.status_code == 502
    assert "notion down" in resp.json()["detail"]


def test_reels_empty_database(tmp_path):
    body = _client(_Store([]), tmp_path=tmp_path).get("/api/reels").json()
    assert body["reels"] == []
    assert body["categories"] == ["Tech", "Fitness"]


# --- /thumbs ---------------------------------------------------------------

def test_thumb_serves_cached_file(tmp_path):
    (tmp_path / "abc.jpg").write_bytes(_JPEG)
    resp = _client(tmp_path=tmp_path).get("/thumbs/abc.jpg")
    assert resp.status_code == 200
    assert resp.content == _JPEG
    assert resp.headers["content-type"] == "image/jpeg"


def test_thumb_missing_returns_404(tmp_path):
    assert _client(tmp_path=tmp_path).get("/thumbs/abc.jpg").status_code == 404


def test_thumb_recovers_a_miss_using_the_stored_url(tmp_path):
    """A cache miss retries the stored CDN URL once before giving up."""
    def cacher(shortcode, url):
        path = tmp_path / f"{shortcode}.jpg"
        path.write_bytes(_JPEG)
        return path

    store = _Store([_row("abc", thumbnail_url="https://cdn/t.jpg")])
    client = _client(store, tmp_path=tmp_path, cacher=cacher)
    client.get("/api/reels")  # populates the shortcode -> URL map
    resp = client.get("/thumbs/abc.jpg")
    assert resp.status_code == 200
    assert resp.content == _JPEG


def test_thumb_recovery_failure_returns_404(tmp_path):
    store = _Store([_row("abc", thumbnail_url="https://cdn/dead.jpg")])
    client = _client(store, tmp_path=tmp_path, cacher=lambda s, u: None)
    client.get("/api/reels")
    assert client.get("/thumbs/abc.jpg").status_code == 404


def test_thumb_recovery_is_skipped_without_a_known_url(tmp_path):
    calls = []
    client = _client(tmp_path=tmp_path,
                     cacher=lambda s, u: calls.append(s))
    assert client.get("/thumbs/unknown.jpg").status_code == 404
    assert calls == []


@pytest.mark.parametrize("shortcode", ["..%2F..%2Fsecret", "a%2Fb", "..", "a.b"])
def test_thumb_rejects_unsafe_shortcodes(tmp_path, shortcode):
    resp = _client(tmp_path=tmp_path).get(f"/thumbs/{shortcode}.jpg")
    assert resp.status_code in (400, 404)


def test_thumb_path_traversal_cannot_read_outside_the_cache(tmp_path):
    """Even a crafted name must not reach a file next to the cache dir."""
    secret = tmp_path.parent / "secret.jpg"
    secret.write_bytes(b"top secret")
    root = tmp_path / "thumbs"
    root.mkdir()
    client = _client(tmp_path=root)
    assert client.get("/thumbs/..%2Fsecret.jpg").status_code in (400, 404)
