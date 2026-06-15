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
