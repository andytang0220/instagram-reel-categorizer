from reel_categorizer.models import ReelMetadata
from reel_categorizer.classifier import (
    build_prompt, parse_response, Classifier, Classification)


def _meta():
    return ReelMetadata(
        shortcode="abc", url="u", caption="High protein meal #mealprep",
        hashtags=["mealprep"], author="cook")


def test_build_prompt_includes_categories_tags_and_caption():
    p = build_prompt(_meta(), ["Food Recipes", "Tech"], ["budget", "quick"])
    assert "Food Recipes" in p
    assert "budget" in p
    assert "mealprep" in p
    assert "title" in p.lower()


def test_parse_response_normalizes_tags():
    text = ('{"category":"Food Recipes","is_new_category":false,'
            '"tags":["High-Protein"," meal-prep "],"reason":"food",'
            '"title":"High-Protein Meal Prep"}')
    c = parse_response(text)
    assert c.category == "Food Recipes"
    assert c.is_new_category is False
    assert c.tags == ["high-protein", "meal-prep"]
    assert c.title == "High-Protein Meal Prep"


def test_parse_response_title_defaults_to_empty():
    text = '{"category":"Tech","is_new_category":false,"tags":["ai"],"reason":"x"}'
    assert parse_response(text).title == ""


def test_parse_response_extracts_embedded_json():
    text = ('Sure!\n{"category":"Tech","is_new_category":true,'
            '"tags":["ai"],"reason":"x"}\nThanks')
    c = parse_response(text)
    assert c.category == "Tech"
    assert c.is_new_category is True


def test_classifier_passes_prompt_to_completion_fn():
    captured = {}

    def fake(system, prompt):
        captured["system"] = system
        captured["prompt"] = prompt
        return '{"category":"Tech","is_new_category":false,"tags":["ai"],"reason":"r"}'

    c = Classifier(fake).classify(_meta(), ["Tech"], ["ai"])
    assert isinstance(c, Classification)
    assert c.category == "Tech"
    assert "Tech" in captured["prompt"]
