from datetime import date

from reel_categorizer.models import ReelMetadata
from reel_categorizer.notion_store import NotionStore, compose_title

_DS_ID = "ds-123"


class _FakeNotion:
    def __init__(self, ds=None, query=None):
        # databases.retrieve returns the data_sources list
        self._db = {"data_sources": [{"id": _DS_ID, "name": "Reels"}]}
        # data_sources.retrieve returns the schema (with Tags options)
        self._ds = ds or {"properties": {"Tags": {"multi_select": {"options": [
            {"name": "budget"}, {"name": "quick"}]}}}}
        self._query = query or {"results": []}
        self.created = []
        self.databases = self._Databases(self)
        self.data_sources = self._DataSources(self)
        self.pages = self._Pages(self)

    class _Databases:
        def __init__(self, outer):
            self._o = outer

        def retrieve(self, database_id):
            return self._o._db

    class _DataSources:
        def __init__(self, outer):
            self._o = outer

        def retrieve(self, data_source_id):
            return self._o._ds

        def query(self, data_source_id, filter):
            return self._o._query

    class _Pages:
        def __init__(self, outer):
            self._o = outer

        def create(self, parent, properties):
            self._o.created.append((parent, properties))
            return {"url": "https://notion.so/page"}


def test_existing_tags():
    assert NotionStore(_FakeNotion(), "db").existing_tags() == ["budget", "quick"]


def test_find_by_shortcode_none():
    assert NotionStore(_FakeNotion(query={"results": []}), "db").find_by_shortcode("a") is None


def test_find_by_shortcode_hit():
    q = {"results": [{"properties": {"Category": {"select": {"name": "Tech"}}}}]}
    assert NotionStore(_FakeNotion(query=q), "db").find_by_shortcode("a") == "Tech"


def test_create_entry_builds_props():
    fake = _FakeNotion()
    store = NotionStore(fake, "db")
    m = ReelMetadata(
        shortcode="abc", url="https://x/reel/abc/", caption="Tacos #food",
        hashtags=["food"], author="chef", post_date=date(2026, 1, 5))
    url = store.create_entry(m, "Food Places", ["tacos", "budget"])
    assert url == "https://notion.so/page"
    parent, props = fake.created[0]
    assert parent == {"type": "data_source_id", "data_source_id": _DS_ID}
    assert props["Category"]["select"]["name"] == "Food Places"
    assert {"name": "tacos"} in props["Tags"]["multi_select"]
    assert props["Shortcode"]["rich_text"][0]["text"]["content"] == "abc"
    assert props["Post Date"]["date"]["start"] == "2026-01-05"


def test_create_entry_without_post_date_omits_property():
    fake = _FakeNotion()
    m = ReelMetadata(shortcode="abc", url="u", caption="hi", author="x")
    NotionStore(fake, "db").create_entry(m, "Tech", ["ai"])
    _, props = fake.created[0]
    assert "Post Date" not in props


def test_compose_title_with_text_uses_inferred():
    assert compose_title("chefjohn", "15-Minute Tacos", has_text=True) == \
        "chefjohn - 15-Minute Tacos"


def test_compose_title_no_text_falls_back_to_untitled():
    assert compose_title("gymrat", "Anything", has_text=False) == "gymrat - Untitled"


def test_compose_title_empty_inferred_falls_back():
    assert compose_title("gymrat", "  ", has_text=True) == "gymrat - Untitled"


def test_compose_title_without_author_drops_prefix():
    assert compose_title("", "Cool Clip", has_text=True) == "Cool Clip"


def test_create_entry_title_is_author_dash_inferred():
    fake = _FakeNotion()
    m = ReelMetadata(shortcode="abc", url="u", caption="Tacos #food",
                     hashtags=["food"], author="chef")
    NotionStore(fake, "db").create_entry(m, "Food Recipes", ["tacos"], "Best Street Tacos")
    _, props = fake.created[0]
    assert props["Title"]["title"][0]["text"]["content"] == "chef - Best Street Tacos"


def test_create_entry_title_untitled_when_no_caption_or_hashtags():
    fake = _FakeNotion()
    m = ReelMetadata(shortcode="abc", url="u", caption="", hashtags=[], author="chef")
    NotionStore(fake, "db").create_entry(m, "Tech", ["ai"], "Model Guessed This")
    _, props = fake.created[0]
    assert props["Title"]["title"][0]["text"]["content"] == "chef - Untitled"
