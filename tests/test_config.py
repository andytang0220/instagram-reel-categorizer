import json
from reel_categorizer.config import (
    load_categories, add_category, load_settings, Settings)


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
