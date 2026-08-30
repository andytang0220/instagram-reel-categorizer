from datetime import date
from reel_categorizer.models import ReelMetadata


def test_reelmetadata_defaults():
    m = ReelMetadata(shortcode="abc", url="https://x/reel/abc/")
    assert m.caption == ""
    assert m.hashtags == []
    assert m.author == ""
    assert m.post_date is None
    assert m.source == ""


def test_reelmetadata_full():
    m = ReelMetadata(
        shortcode="abc", url="u", caption="hi #food", hashtags=["food"],
        author="bob", post_date=date(2026, 1, 1), source="ytdlp",
    )
    assert m.author == "bob"
    assert m.post_date == date(2026, 1, 1)
    assert m.source == "ytdlp"


def test_reelmetadata_thumbnail_and_views_default_empty():
    m = ReelMetadata(shortcode="abc", url="https://x/reel/abc/")
    assert m.thumbnail_url == ""
    assert m.view_count is None


def test_reelmetadata_carries_thumbnail_and_views():
    m = ReelMetadata(
        shortcode="abc", url="u",
        thumbnail_url="https://cdn/thumb.jpg", view_count=12345,
    )
    assert m.thumbnail_url == "https://cdn/thumb.jpg"
    assert m.view_count == 12345
