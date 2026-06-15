import pytest
from reel_categorizer.urls import extract_shortcode, canonical_url, InvalidReelURL


@pytest.mark.parametrize("url,expected", [
    ("https://www.instagram.com/reel/C1a2b3/", "C1a2b3"),
    ("https://instagram.com/reels/C1a2b3/?igshid=xyz", "C1a2b3"),
    ("https://www.instagram.com/p/Abc_-123/", "Abc_-123"),
    ("http://instagram.com/reel/XyZ9/", "XyZ9"),
])
def test_extract_shortcode(url, expected):
    assert extract_shortcode(url) == expected


def test_extract_shortcode_invalid():
    with pytest.raises(InvalidReelURL):
        extract_shortcode("https://example.com/foo")


def test_canonical_url():
    assert canonical_url("C1a2b3") == "https://www.instagram.com/reel/C1a2b3/"
