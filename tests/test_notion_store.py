from datetime import date

from reel_categorizer.models import ReelMetadata
from reel_categorizer.notion_store import NotionStore


class _FakeNotion:
    def __init__(self, db=None, query=None):
        self._db = db or {"properties": {"Tags": {"multi_select": {"options": [
            {"name": "budget"}, {"name": "quick"}]}}}}
        self._query = query or {"results": []}
        self.created = []
        self.databases = self._Databases(self)
        self.pages = self._Pages(self)

    class _Databases:
        def __init__(self, outer):
            self._o = outer

        def retrieve(self, database_id):
            return self._o._db

        def query(self, database_id, filter):
            return self._o._query

    class _Pages:
        def __init__(self, outer):
            self._o = outer

        def create(self, parent, properties):
            self._o.created.append(properties)
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
    props = fake.created[0]
    assert props["Category"]["select"]["name"] == "Food Places"
    assert {"name": "tacos"} in props["Tags"]["multi_select"]
    assert props["Shortcode"]["rich_text"][0]["text"]["content"] == "abc"
    assert props["Post Date"]["date"]["start"] == "2026-01-05"


def test_create_entry_without_post_date_omits_property():
    fake = _FakeNotion()
    m = ReelMetadata(shortcode="abc", url="u", caption="hi", author="x")
    NotionStore(fake, "db").create_entry(m, "Tech", ["ai"])
    assert "Post Date" not in fake.created[0]
