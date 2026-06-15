from __future__ import annotations

from .models import ReelMetadata


class NotionStore:
    def __init__(self, client, database_id: str):
        self._client = client
        self._db = database_id

    def existing_tags(self) -> list[str]:
        db = self._client.databases.retrieve(self._db)
        prop = db.get("properties", {}).get("Tags", {})
        options = prop.get("multi_select", {}).get("options", [])
        return [o["name"] for o in options]

    def find_by_shortcode(self, shortcode: str) -> str | None:
        res = self._client.databases.query(
            database_id=self._db,
            filter={"property": "Shortcode",
                    "rich_text": {"equals": shortcode}},
        )
        results = res.get("results", [])
        if not results:
            return None
        sel = results[0]["properties"].get("Category", {}).get("select")
        return sel["name"] if sel else "Uncategorized"

    def create_entry(
        self, meta: ReelMetadata, category: str, tags: list[str]
    ) -> str:
        title = meta.caption[:80] or meta.author or meta.shortcode
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
            parent={"database_id": self._db}, properties=props
        )
        return page.get("url", "")
