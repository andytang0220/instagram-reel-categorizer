from reel_categorizer.bot import extract_urls


def test_extract_urls_finds_links():
    text = "check https://www.instagram.com/reel/abc/ and https://x.com/y"
    assert extract_urls(text) == [
        "https://www.instagram.com/reel/abc/", "https://x.com/y"]


def test_extract_urls_none():
    assert extract_urls("just text") == []
    assert extract_urls(None) == []
