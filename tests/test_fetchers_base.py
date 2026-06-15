from reel_categorizer.fetchers.base import parse_hashtags


def test_parse_hashtags_lowercases_strips_hash():
    assert parse_hashtags("Love this #Food #MealPrep yum") == ["food", "mealprep"]


def test_parse_hashtags_empty_and_none():
    assert parse_hashtags("") == []
    assert parse_hashtags(None) == []
