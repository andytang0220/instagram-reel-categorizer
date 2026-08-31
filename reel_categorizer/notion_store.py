from __future__ import annotations

from dataclasses import dataclass, field

from .models import ReelMetadata
from .urls import InvalidReelURL, extract_shortcode


@dataclass
class ReelRow:
    """A saved reel, read back out of Notion for display.

    Dates stay as ISO strings because the only consumer is the web API, which
    hands them straight to the browser.
    """

    page_id: str = ""
    shortcode: str = ""
    title: str = ""
    url: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    author: str = ""
    likes: int | None = None
    post_date: str = ""
    date_added: str = ""
    thumbnail_url: str = ""


def _plain_text(prop: dict | None, key: str) -> str:
    """Join a Notion title/rich_text array, which Notion splits into chunks."""
    if not prop:
        return ""
    return "".join(chunk.get("plain_text", "") for chunk in prop.get(key) or [])


def parse_row(page: dict) -> ReelRow:
    """Map a Notion page to a ReelRow.

    Every property is treated as optional: rows saved before a property
    existed simply come back with the field empty.
    """
    props = page.get("properties") or {}

    def prop(name: str) -> dict:
        return props.get(name) or {}

    select = prop("Category").get("select") or {}
    date_prop = prop("Post Date").get("date") or {}
    url = prop("Reel URL").get("url") or ""

    shortcode = _plain_text(prop("Shortcode"), "rich_text")
    if not shortcode and url:
        try:
            shortcode = extract_shortcode(url)
        except InvalidReelURL:
            shortcode = ""

    return ReelRow(
        page_id=page.get("id", ""),
        shortcode=shortcode,
        title=_plain_text(prop("Title"), "title"),
        url=url,
        category=select.get("name") or "",
        tags=[t["name"] for t in prop("Tags").get("multi_select") or []],
        author=_plain_text(prop("Author"), "rich_text"),
        likes=prop("Likes").get("number"),
        post_date=date_prop.get("start") or "",
        # Rows predating the `Date Added` property still sort correctly.
        date_added=(prop("Date Added").get("created_time")
                    or page.get("created_time", "")),
        thumbnail_url=prop("Thumbnail URL").get("url") or "",
    )


def compose_title(author: str, inferred_title: str, has_text: bool) -> str:
    """Build the Notion Title: "username - Inferred Title".

    Uses the best-effort inferred title when the reel had any caption/hashtags
    to work with; falls back to "Untitled" when there was nothing to infer from
    (or the model returned nothing). Drops the "username - " prefix if the
    author is unknown.
    """
    title = inferred_title.strip() if (has_text and inferred_title.strip()) else "Untitled"
    return f"{author} - {title}" if author else title


class NotionStore:
    """Reads/writes the reel database via Notion's data-sources API.

    A Notion database exposes one or more data sources; queries, schema, and
    page creation all happen against a data source, resolved here from the
    database id.
    """

    def __init__(self, client, database_id: str):
        self._client = client
        self._db = database_id
        self._ds_id: str | None = None

    def _data_source_id(self) -> str:
        if self._ds_id is None:
            db = self._client.databases.retrieve(self._db)
            sources = db.get("data_sources", [])
            if not sources:
                raise RuntimeError(
                    f"Notion database {self._db} has no data sources"
                )
            self._ds_id = sources[0]["id"]
        return self._ds_id

    def existing_tags(self) -> list[str]:
        ds = self._client.data_sources.retrieve(
            data_source_id=self._data_source_id()
        )
        prop = ds.get("properties", {}).get("Tags", {})
        options = prop.get("multi_select", {}).get("options", [])
        return [o["name"] for o in options]

    def find_by_shortcode(self, shortcode: str) -> str | None:
        res = self._client.data_sources.query(
            data_source_id=self._data_source_id(),
            filter={"property": "Shortcode",
                    "rich_text": {"equals": shortcode}},
        )
        results = res.get("results", [])
        if not results:
            return None
        sel = results[0]["properties"].get("Category", {}).get("select")
        return sel["name"] if sel else "Uncategorized"

    def create_entry(
        self, meta: ReelMetadata, category: str, tags: list[str],
        inferred_title: str = "",
    ) -> str:
        has_text = bool(meta.caption.strip() or meta.hashtags)
        title = compose_title(meta.author, inferred_title, has_text)
        props = {
            "Title": {"title": [{"text": {"content": title}}]},
            "Category": {"select": {"name": category}},
            "Tags": {"multi_select": [{"name": t} for t in tags]},
            "Caption": {"rich_text": [{"text": {"content": meta.caption[:2000]}}]},
            "Hashtags": {"rich_text": [{"text": {"content":
                " ".join("#" + h for h in meta.hashtags)}}]},
            "Author": {"rich_text": [{"text": {"content": meta.author}}]},
            "Reel URL": {"url": meta.url},
            "Shortcode": {"rich_text": [{"text": {"content": meta.shortcode}}]},
        }
        if meta.post_date:
            props["Post Date"] = {"date": {"start": meta.post_date.isoformat()}}
        if meta.like_count is not None:
            props["Likes"] = {"number": meta.like_count}
        if meta.thumbnail_url:
            props["Thumbnail URL"] = {"url": meta.thumbnail_url}
        page = self._client.pages.create(
            parent={"type": "data_source_id",
                    "data_source_id": self._data_source_id()},
            properties=props,
        )
        return page.get("url", "")

    def query_all(self) -> list[ReelRow]:
        """Every saved reel, newest first."""
        rows: list[ReelRow] = []
        cursor = None
        while True:
            res = self._client.data_sources.query(
                data_source_id=self._data_source_id(),
                sorts=[{"timestamp": "created_time", "direction": "descending"}],
                start_cursor=cursor,
                page_size=100,
            )
            rows.extend(parse_row(p) for p in res.get("results", []))
            if not res.get("has_more"):
                return rows
            cursor = res.get("next_cursor")
            if not cursor:
                return rows

    def update_entry(
        self, page_id: str, likes: int | None = None,
        thumbnail_url: str | None = None,
    ) -> None:
        """Patch only the properties actually supplied. Used by the backfill."""
        props = {}
        if likes is not None:
            props["Likes"] = {"number": likes}
        if thumbnail_url:
            props["Thumbnail URL"] = {"url": thumbnail_url}
        if not props:
            return
        self._client.pages.update(page_id=page_id, properties=props)
