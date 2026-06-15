from __future__ import annotations

from .models import ReelMetadata


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
        page = self._client.pages.create(
            parent={"type": "data_source_id",
                    "data_source_id": self._data_source_id()},
            properties=props,
        )
        return page.get("url", "")
