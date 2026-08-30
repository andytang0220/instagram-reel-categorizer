from reel_categorizer.pipeline import Pipeline
from reel_categorizer.models import ReelMetadata
from reel_categorizer.fetchers.base import MetadataFetcher, FetchError
from reel_categorizer.classifier import Classification


class _Fetcher(MetadataFetcher):
    name = "f"

    def __init__(self, meta=None, err=False):
        self._m = meta
        self._err = err

    def fetch(self, url, shortcode):
        if self._err:
            raise FetchError("x")
        return self._m or ReelMetadata(shortcode=shortcode, url=url, caption="cap")


class _Classifier:
    def __init__(self, result):
        self._r = result

    def classify(self, meta, cats, tags):
        return self._r


class _Store:
    def __init__(self, existing=None, tags=None):
        self._existing = existing
        self._tags = tags or []
        self.created = []

    def find_by_shortcode(self, sc):
        return self._existing

    def existing_tags(self):
        return self._tags

    def create_entry(self, meta, category, tags, inferred_title=""):
        self.created.append((category, tags, inferred_title))
        return "https://notion/p"


def _pipe(fetcher, classifier, store, cats=("Tech", "Food Recipes")):
    return Pipeline([fetcher], classifier, store, lambda: list(cats))


def test_invalid_url():
    r = _pipe(_Fetcher(), _Classifier(None), _Store()).process("https://example.com/x")
    assert r.kind == "invalid"


def test_duplicate():
    r = _pipe(_Fetcher(), _Classifier(None), _Store(existing="Tech")).process(
        "https://www.instagram.com/reel/abc/")
    assert r.kind == "duplicate"
    assert r.category == "Tech"


def test_fetch_error():
    r = _pipe(_Fetcher(err=True), _Classifier(None), _Store()).process(
        "https://www.instagram.com/reel/abc/")
    assert r.kind == "error"


def test_saved():
    c = Classification("Tech", False, ["ai"], "r", "Cool Gadget Demo")
    store = _Store()
    r = _pipe(_Fetcher(), _Classifier(c), store).process(
        "https://www.instagram.com/reel/abc/")
    assert r.kind == "saved"
    assert r.category == "Tech"
    assert store.created[0][0] == "Tech"
    assert store.created[0][2] == "Cool Gadget Demo"  # inferred title threaded through
    assert r.title == "Cool Gadget Demo"


def test_needs_category_when_new():
    c = Classification("Cooking", True, ["tacos"], "r")
    store = _Store()
    r = _pipe(_Fetcher(), _Classifier(c), store).process(
        "https://www.instagram.com/reel/abc/")
    assert r.kind == "needs_category"
    assert r.proposed_category == "Cooking"
    assert r.tags == ["tacos"]
    assert store.created == []


def test_needs_category_when_unknown_category():
    c = Classification("Cooking", False, ["tacos"], "r")  # not in list
    store = _Store()
    r = _pipe(_Fetcher(), _Classifier(c), store).process(
        "https://www.instagram.com/reel/abc/")
    assert r.kind == "needs_category"


def test_save_persists():
    store = _Store()
    p = _pipe(_Fetcher(), _Classifier(None), store)
    out = p.save(ReelMetadata(shortcode="abc", url="u"), "Tech", ["ai"], "My Title")
    assert out == "https://notion/p"
    assert store.created[0] == ("Tech", ["ai"], "My Title")


class _FailingStore(_Store):
    def create_entry(self, meta, category, tags, inferred_title=""):
        raise RuntimeError("notion down")


def test_save_failure_returns_error():
    c = Classification("Tech", False, ["ai"], "r")
    r = _pipe(_Fetcher(), _Classifier(c), _FailingStore()).process(
        "https://www.instagram.com/reel/abc/")
    assert r.kind == "error"
    assert "Notion" in r.message


class _Cacher:
    """Records (shortcode, url) pairs the pipeline asks to cache."""

    def __init__(self, err=False):
        self.calls = []
        self._err = err

    def __call__(self, shortcode, url):
        self.calls.append((shortcode, url))
        if self._err:
            raise RuntimeError("disk full")
        return "thumbnails/x.jpg"


def _pipe_with_cacher(fetcher, classifier, store, cacher):
    return Pipeline([fetcher], classifier, store,
                    lambda: ["Tech", "Food Recipes"], cache_thumbnail=cacher)


def test_process_caches_thumbnail_after_saving():
    meta = ReelMetadata(shortcode="abc", url="u", caption="cap",
                        thumbnail_url="https://cdn/t.jpg")
    cacher = _Cacher()
    _pipe_with_cacher(_Fetcher(meta), _Classifier(
        Classification("Tech", False, ["ai"], "r")), _Store(), cacher).process(
        "https://www.instagram.com/reel/abc/")
    assert cacher.calls == [("abc", "https://cdn/t.jpg")]


def test_thumbnail_failure_does_not_break_a_save():
    """A dead CDN URL must not turn a saved reel into an error."""
    meta = ReelMetadata(shortcode="abc", url="u", caption="cap",
                        thumbnail_url="https://cdn/t.jpg")
    r = _pipe_with_cacher(_Fetcher(meta), _Classifier(
        Classification("Tech", False, ["ai"], "r")), _Store(),
        _Cacher(err=True)).process("https://www.instagram.com/reel/abc/")
    assert r.kind == "saved"


def test_no_thumbnail_url_skips_caching():
    cacher = _Cacher()
    _pipe_with_cacher(_Fetcher(), _Classifier(
        Classification("Tech", False, ["ai"], "r")), _Store(), cacher).process(
        "https://www.instagram.com/reel/abc/")
    assert cacher.calls == []


def test_save_caches_thumbnail():
    cacher = _Cacher()
    p = _pipe_with_cacher(_Fetcher(), _Classifier(None), _Store(), cacher)
    meta = ReelMetadata(shortcode="abc", url="u",
                        thumbnail_url="https://cdn/t.jpg")
    p.save(meta, "Tech", ["ai"], "My Title")
    assert cacher.calls == [("abc", "https://cdn/t.jpg")]


def test_failed_save_does_not_cache_thumbnail():
    cacher = _Cacher()
    meta = ReelMetadata(shortcode="abc", url="u", caption="cap",
                        thumbnail_url="https://cdn/t.jpg")
    r = _pipe_with_cacher(_Fetcher(meta), _Classifier(
        Classification("Tech", False, ["ai"], "r")), _FailingStore(),
        cacher).process("https://www.instagram.com/reel/abc/")
    assert r.kind == "error"
    assert cacher.calls == []
