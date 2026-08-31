from datetime import date

from reel_categorizer.models import ReelMetadata
from reel_categorizer.notion_store import NotionStore, compose_title, parse_row

_DS_ID = "ds-123"


class _FakeNotion:
    def __init__(self, ds=None, query=None, pages_seq=None):
        # databases.retrieve returns the data_sources list
        self._db = {"data_sources": [{"id": _DS_ID, "name": "Reels"}]}
        # data_sources.retrieve returns the schema (with Tags options)
        self._ds = ds or {"properties": {"Tags": {"multi_select": {"options": [
            {"name": "budget"}, {"name": "quick"}]}}}}
        self._query = query or {"results": []}
        # Successive responses for paginated query_all calls.
        self._pages_seq = list(pages_seq or [])
        self.query_calls = []
        self.created = []
        self.updated = []
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

        def query(self, data_source_id, **kwargs):
            self._o.query_calls.append(kwargs)
            if self._o._pages_seq:
                return self._o._pages_seq.pop(0)
            return self._o._query

    class _Pages:
        def __init__(self, outer):
            self._o = outer

        def create(self, parent, properties):
            self._o.created.append((parent, properties))
            return {"url": "https://notion.so/page"}

        def update(self, page_id, properties):
            self._o.updated.append((page_id, properties))
            return {"id": page_id}


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


# --- new properties on create ---------------------------------------------

def test_create_entry_writes_likes_and_thumbnail_url():
    fake = _FakeNotion()
    m = ReelMetadata(shortcode="abc", url="u", caption="hi",
                     thumbnail_url="https://cdn/t.jpg", like_count=5000)
    NotionStore(fake, "db").create_entry(m, "Tech", ["ai"])
    _, props = fake.created[0]
    assert props["Likes"]["number"] == 5000
    assert props["Thumbnail URL"]["url"] == "https://cdn/t.jpg"


def test_create_entry_omits_likes_and_thumbnail_when_absent():
    fake = _FakeNotion()
    m = ReelMetadata(shortcode="abc", url="u", caption="hi")
    NotionStore(fake, "db").create_entry(m, "Tech", ["ai"])
    _, props = fake.created[0]
    assert "Likes" not in props
    assert "Thumbnail URL" not in props


def test_create_entry_writes_zero_likes():
    """0 likes is real data, not a missing value."""
    fake = _FakeNotion()
    m = ReelMetadata(shortcode="abc", url="u", caption="hi", like_count=0)
    NotionStore(fake, "db").create_entry(m, "Tech", ["ai"])
    _, props = fake.created[0]
    assert props["Likes"]["number"] == 0


# --- parse_row -------------------------------------------------------------

def _page(**props):
    return {"id": "page-1", "created_time": "2026-03-01T12:00:00.000Z",
            "properties": props}


def test_parse_row_maps_every_property():
    row = parse_row(_page(
        **{"Title": {"type": "title",
                     "title": [{"plain_text": "chef - Best Tacos"}]},
           "Category": {"type": "select", "select": {"name": "Food Recipes"}},
           "Tags": {"type": "multi_select",
                    "multi_select": [{"name": "tacos"}, {"name": "budget"}]},
           "Author": {"type": "rich_text",
                      "rich_text": [{"plain_text": "chef"}]},
           "Reel URL": {"type": "url", "url": "https://instagram.com/reel/abc/"},
           "Shortcode": {"type": "rich_text",
                         "rich_text": [{"plain_text": "abc"}]},
           "Post Date": {"type": "date", "date": {"start": "2026-02-14"}},
           "Date Added": {"type": "created_time",
                          "created_time": "2026-02-15T09:30:00.000Z"},
           "Likes": {"type": "number", "number": 12345},
           "Thumbnail URL": {"type": "url", "url": "https://cdn/t.jpg"}}))
    assert row.page_id == "page-1"
    assert row.title == "chef - Best Tacos"
    assert row.category == "Food Recipes"
    assert row.tags == ["tacos", "budget"]
    assert row.author == "chef"
    assert row.url == "https://instagram.com/reel/abc/"
    assert row.shortcode == "abc"
    assert row.post_date == "2026-02-14"
    assert row.date_added == "2026-02-15T09:30:00.000Z"
    assert row.likes == 12345
    assert row.thumbnail_url == "https://cdn/t.jpg"


def test_parse_row_tolerates_missing_properties():
    row = parse_row(_page())
    assert row.page_id == "page-1"
    assert row.title == ""
    assert row.category == ""
    assert row.tags == []
    assert row.author == ""
    assert row.url == ""
    assert row.shortcode == ""
    assert row.post_date == ""
    assert row.likes is None
    assert row.thumbnail_url == ""


def test_parse_row_falls_back_to_page_created_time():
    """Rows predating the `Date Added` property still sort correctly."""
    assert parse_row(_page()).date_added == "2026-03-01T12:00:00.000Z"


def test_parse_row_tolerates_null_valued_properties():
    row = parse_row(_page(
        **{"Category": {"type": "select", "select": None},
           "Reel URL": {"type": "url", "url": None},
           "Post Date": {"type": "date", "date": None},
           "Likes": {"type": "number", "number": None},
           "Thumbnail URL": {"type": "url", "url": None}}))
    assert row.category == ""
    assert row.url == ""
    assert row.post_date == ""
    assert row.likes is None
    assert row.thumbnail_url == ""


def test_parse_row_joins_split_rich_text():
    """Notion splits long text into several rich_text chunks."""
    row = parse_row(_page(**{"Author": {
        "type": "rich_text",
        "rich_text": [{"plain_text": "chef"}, {"plain_text": "john"}]}}))
    assert row.author == "chefjohn"


def test_parse_row_derives_shortcode_from_url_when_property_missing():
    row = parse_row(_page(**{"Reel URL": {
        "type": "url", "url": "https://www.instagram.com/reel/XyZ123/"}}))
    assert row.shortcode == "XyZ123"


# --- query_all -------------------------------------------------------------

def _result_page(page_id, category="Tech"):
    return {"id": page_id, "created_time": "2026-03-01T12:00:00.000Z",
            "properties": {"Category": {"type": "select",
                                        "select": {"name": category}},
                           "Shortcode": {"type": "rich_text",
                                         "rich_text": [{"plain_text": page_id}]}}}


def test_query_all_returns_parsed_rows():
    fake = _FakeNotion(query={"results": [_result_page("a"), _result_page("b")],
                              "has_more": False})
    rows = NotionStore(fake, "db").query_all()
    assert [r.shortcode for r in rows] == ["a", "b"]
    assert rows[0].category == "Tech"


def test_query_all_follows_pagination():
    fake = _FakeNotion(pages_seq=[
        {"results": [_result_page("a")], "has_more": True, "next_cursor": "c1"},
        {"results": [_result_page("b")], "has_more": True, "next_cursor": "c2"},
        {"results": [_result_page("c")], "has_more": False, "next_cursor": None},
    ])
    rows = NotionStore(fake, "db").query_all()
    assert [r.shortcode for r in rows] == ["a", "b", "c"]
    assert fake.query_calls[0].get("start_cursor") is None
    assert fake.query_calls[1]["start_cursor"] == "c1"
    assert fake.query_calls[2]["start_cursor"] == "c2"


def test_query_all_sorts_newest_first():
    fake = _FakeNotion(query={"results": [], "has_more": False})
    NotionStore(fake, "db").query_all()
    assert fake.query_calls[0]["sorts"] == [
        {"timestamp": "created_time", "direction": "descending"}]


def test_query_all_empty_database():
    fake = _FakeNotion(query={"results": [], "has_more": False})
    assert NotionStore(fake, "db").query_all() == []


# --- update_entry ----------------------------------------------------------

def test_update_entry_patches_both_properties():
    fake = _FakeNotion()
    NotionStore(fake, "db").update_entry(
        "page-1", likes=42, thumbnail_url="https://cdn/t.jpg")
    page_id, props = fake.updated[0]
    assert page_id == "page-1"
    assert props["Likes"]["number"] == 42
    assert props["Thumbnail URL"]["url"] == "https://cdn/t.jpg"


def test_update_entry_patches_only_what_is_supplied():
    fake = _FakeNotion()
    NotionStore(fake, "db").update_entry("page-1", likes=42)
    _, props = fake.updated[0]
    assert "Likes" in props
    assert "Thumbnail URL" not in props


def test_update_entry_with_nothing_to_do_skips_the_call():
    fake = _FakeNotion()
    NotionStore(fake, "db").update_entry("page-1")
    assert fake.updated == []
