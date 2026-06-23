import json
from reel_categorizer.config import (
    load_categories, add_category, remove_category, load_settings, Settings,
    match_category)


def test_remove_category_case_insensitive(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(["Food Recipes", "Tech", "Sports"]))
    cats, removed = remove_category("tech", p)
    assert removed is True
    assert cats == ["Food Recipes", "Sports"]
    assert json.loads(p.read_text()) == ["Food Recipes", "Sports"]


def test_remove_category_absent_is_noop(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(["Tech"]))
    cats, removed = remove_category("Cooking", p)
    assert removed is False
    assert cats == ["Tech"]
    assert json.loads(p.read_text()) == ["Tech"]


def test_match_category_case_insensitive_returns_canonical():
    cats = ["Food Recipes", "Tech"]
    assert match_category("tech", cats) == "Tech"
    assert match_category("  FOOD recipes ", cats) == "Food Recipes"


def test_match_category_no_match_returns_none():
    assert match_category("Cooking", ["Tech", "Sports"]) is None
    assert match_category("   ", ["Tech"]) is None


def test_load_categories(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(["Fitness", "Tech"]))
    assert load_categories(p) == ["Fitness", "Tech"]


def test_add_category_appends(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(["Fitness"]))
    assert add_category("Gaming", p) == ["Fitness", "Gaming"]
    assert json.loads(p.read_text()) == ["Fitness", "Gaming"]


def test_add_category_idempotent(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(["Fitness"]))
    add_category("Fitness", p)
    assert json.loads(p.read_text()) == ["Fitness"]


def test_load_settings_reads_env():
    env = {
        "TELEGRAM_BOT_TOKEN": "t", "ANTHROPIC_API_KEY": "a",
        "NOTION_TOKEN": "n", "NOTION_DATABASE_ID": "d",
    }
    s = load_settings(env)
    assert isinstance(s, Settings)
    assert s.telegram_token == "t"
    assert s.notion_database_id == "d"
    assert s.apify_token is None


def test_load_settings_optional_apify():
    env = {
        "TELEGRAM_BOT_TOKEN": "t", "ANTHROPIC_API_KEY": "a",
        "NOTION_TOKEN": "n", "NOTION_DATABASE_ID": "d", "APIFY_TOKEN": "k",
    }
    assert load_settings(env).apify_token == "k"
