# Instagram Reel Categorizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Telegram bot that takes an Instagram reel link, fetches its text metadata, classifies it into a category with searchable tags via Claude, and files it as a row in a Notion database.

**Architecture:** A single Python process runs a long-polling Telegram bot. A pure `Pipeline` orchestrates isolated, individually-tested modules: URL parsing → metadata fetch (yt-dlp primary, Apify fallback) → Claude classification → Notion write. External services sit behind narrow interfaces so every unit is mockable.

**Tech Stack:** Python 3.11+, python-telegram-bot, yt-dlp, anthropic, notion-client, requests, python-dotenv, pytest.

---

## File Structure

```
instagram-reel-categorizer/
├── requirements.txt
├── pytest.ini
├── categories.json                 # seeded category list (user-editable)
├── .env.example
├── README.md
├── reel_categorizer/
│   ├── __init__.py
│   ├── models.py                   # ReelMetadata dataclass
│   ├── urls.py                     # shortcode parsing / validation
│   ├── config.py                   # settings + categories load/add
│   ├── classifier.py               # Claude call -> Classification
│   ├── notion_store.py             # dedupe, tag vocab, write row
│   ├── pipeline.py                 # orchestration (no Telegram)
│   ├── bot.py                      # Telegram glue + entrypoint
│   └── fetchers/
│       ├── __init__.py             # get_metadata() ordering
│       ├── base.py                 # MetadataFetcher, FetchError, parse_hashtags
│       ├── ytdlp_fetcher.py
│       └── apify_fetcher.py
└── tests/
    ├── test_models.py
    ├── test_urls.py
    ├── test_config.py
    ├── test_fetchers_base.py
    ├── test_ytdlp_fetcher.py
    ├── test_apify_fetcher.py
    ├── test_get_metadata.py
    ├── test_classifier.py
    ├── test_notion_store.py
    ├── test_pipeline.py
    └── test_bot.py
```

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `categories.json`, `.env.example`
- Create: `reel_categorizer/__init__.py`, `reel_categorizer/fetchers/__init__.py` (empty for now)

- [ ] **Step 1: Create `requirements.txt`**

```
python-telegram-bot>=21,<22
yt-dlp>=2024.1.1
anthropic>=0.40
notion-client>=2.2
requests>=2.31
python-dotenv>=1.0
pytest>=8.0
pytest-asyncio>=0.23
```

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
pythonpath = .
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 3: Create `categories.json`**

```json
[
  "Food Recipes",
  "Food Places",
  "Fitness",
  "Tech",
  "Sports",
  "Gaming"
]
```

- [ ] **Step 4: Create `.env.example`**

```
TELEGRAM_BOT_TOKEN=
ANTHROPIC_API_KEY=
NOTION_TOKEN=
NOTION_DATABASE_ID=
# Optional — enables the paid Apify fallback fetcher
APIFY_TOKEN=
```

- [ ] **Step 5: Create empty package markers**

Create `reel_categorizer/__init__.py` with a single line:

```python
"""Instagram reel categorizer package."""
```

Create `reel_categorizer/fetchers/__init__.py` empty (it gets `get_metadata` in Task 8):

```python
```

- [ ] **Step 6: Create and activate a virtualenv, install deps**

Run:
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```
Expected: installs succeed. (On PowerShell use `.venv\Scripts\python`.)

- [ ] **Step 7: Verify pytest runs (no tests yet)**

Run: `.venv/Scripts/python -m pytest -q`
Expected: "no tests ran" exit 5 (acceptable) — confirms pytest + config load.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt pytest.ini categories.json .env.example reel_categorizer/__init__.py reel_categorizer/fetchers/__init__.py
git commit -m "chore: scaffold reel categorizer project"
```

---

## Task 2: `ReelMetadata` model

**Files:**
- Create: `reel_categorizer/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: reel_categorizer.models`.

- [ ] **Step 3: Write minimal implementation**

`reel_categorizer/models.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ReelMetadata:
    """Normalized reel metadata returned by every fetcher."""

    shortcode: str
    url: str
    caption: str = ""
    hashtags: list[str] = field(default_factory=list)
    author: str = ""
    post_date: date | None = None
    source: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add reel_categorizer/models.py tests/test_models.py
git commit -m "feat: add ReelMetadata model"
```

---

## Task 3: URL parsing

**Files:**
- Create: `reel_categorizer/urls.py`
- Test: `tests/test_urls.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_urls.py -v`
Expected: FAIL with `ModuleNotFoundError: reel_categorizer.urls`.

- [ ] **Step 3: Write minimal implementation**

`reel_categorizer/urls.py`:
```python
from __future__ import annotations

import re

_SHORTCODE_RE = re.compile(r"instagram\.com/(?:reel|reels|p)/([A-Za-z0-9_-]+)")


class InvalidReelURL(ValueError):
    """Raised when a URL is not a recognizable Instagram reel/post link."""


def extract_shortcode(url: str) -> str:
    match = _SHORTCODE_RE.search(url or "")
    if not match:
        raise InvalidReelURL(f"Not a recognized Instagram reel URL: {url!r}")
    return match.group(1)


def canonical_url(shortcode: str) -> str:
    return f"https://www.instagram.com/reel/{shortcode}/"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_urls.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add reel_categorizer/urls.py tests/test_urls.py
git commit -m "feat: add reel URL parsing"
```

---

## Task 4: Config (settings + categories)

**Files:**
- Create: `reel_categorizer/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: reel_categorizer.config`.

- [ ] **Step 3: Write minimal implementation**

`reel_categorizer/config.py`:
```python
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_CATEGORIES_PATH = Path(os.getenv("CATEGORIES_PATH", "categories.json"))


def load_categories(path: Path = DEFAULT_CATEGORIES_PATH) -> list[str]:
    return json.loads(Path(path).read_text())


def add_category(name: str, path: Path = DEFAULT_CATEGORIES_PATH) -> list[str]:
    path = Path(path)
    cats = load_categories(path)
    if name not in cats:
        cats.append(name)
        path.write_text(json.dumps(cats, indent=2))
    return cats


@dataclass
class Settings:
    telegram_token: str
    anthropic_api_key: str
    notion_token: str
    notion_database_id: str
    apify_token: str | None = None


def load_settings(env: dict | None = None) -> Settings:
    env = env if env is not None else os.environ
    return Settings(
        telegram_token=env["TELEGRAM_BOT_TOKEN"],
        anthropic_api_key=env["ANTHROPIC_API_KEY"],
        notion_token=env["NOTION_TOKEN"],
        notion_database_id=env["NOTION_DATABASE_ID"],
        apify_token=env.get("APIFY_TOKEN") or None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add reel_categorizer/config.py tests/test_config.py
git commit -m "feat: add config loading for settings and categories"
```

---

## Task 5: Fetcher base (interface + hashtag parsing)

**Files:**
- Create: `reel_categorizer/fetchers/base.py`
- Test: `tests/test_fetchers_base.py`

- [ ] **Step 1: Write the failing test**

```python
from reel_categorizer.fetchers.base import parse_hashtags


def test_parse_hashtags_lowercases_strips_hash():
    assert parse_hashtags("Love this #Food #MealPrep yum") == ["food", "mealprep"]


def test_parse_hashtags_empty_and_none():
    assert parse_hashtags("") == []
    assert parse_hashtags(None) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_fetchers_base.py -v`
Expected: FAIL with `ModuleNotFoundError: reel_categorizer.fetchers.base`.

- [ ] **Step 3: Write minimal implementation**

`reel_categorizer/fetchers/base.py`:
```python
from __future__ import annotations

import re
from abc import ABC, abstractmethod

from ..models import ReelMetadata

_HASHTAG_RE = re.compile(r"#(\w+)")


def parse_hashtags(caption: str | None) -> list[str]:
    return [h.lower() for h in _HASHTAG_RE.findall(caption or "")]


class FetchError(Exception):
    """Raised when a fetcher cannot retrieve reel metadata."""


class MetadataFetcher(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, url: str, shortcode: str) -> ReelMetadata:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_fetchers_base.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add reel_categorizer/fetchers/base.py tests/test_fetchers_base.py
git commit -m "feat: add fetcher base interface and hashtag parsing"
```

---

## Task 6: yt-dlp fetcher

**Files:**
- Create: `reel_categorizer/fetchers/ytdlp_fetcher.py`
- Test: `tests/test_ytdlp_fetcher.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

import pytest

from reel_categorizer.fetchers.ytdlp_fetcher import YtdlpFetcher
from reel_categorizer.fetchers.base import FetchError


class _FakeYDL:
    def __init__(self, info):
        self._info = info

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        return self._info


def test_ytdlp_normalizes_info():
    info = {"description": "Best tacos #food #tacos",
            "uploader": "chef", "upload_date": "20260110"}
    f = YtdlpFetcher(ydl_factory=lambda: _FakeYDL(info))
    m = f.fetch("https://www.instagram.com/reel/abc/", "abc")
    assert m.caption == "Best tacos #food #tacos"
    assert m.hashtags == ["food", "tacos"]
    assert m.author == "chef"
    assert m.post_date == date(2026, 1, 10)
    assert m.source == "ytdlp"


def test_ytdlp_handles_missing_fields():
    f = YtdlpFetcher(ydl_factory=lambda: _FakeYDL({}))
    m = f.fetch("https://www.instagram.com/reel/abc/", "abc")
    assert m.caption == ""
    assert m.author == ""
    assert m.post_date is None


def test_ytdlp_raises_fetcherror():
    class _Boom:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, *a, **k):
            raise RuntimeError("blocked")

    f = YtdlpFetcher(ydl_factory=lambda: _Boom())
    with pytest.raises(FetchError):
        f.fetch("u", "abc")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_ytdlp_fetcher.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`reel_categorizer/fetchers/ytdlp_fetcher.py`:
```python
from __future__ import annotations

from datetime import datetime

import yt_dlp

from ..models import ReelMetadata
from .base import FetchError, MetadataFetcher, parse_hashtags


def _default_factory():
    return yt_dlp.YoutubeDL(
        {"quiet": True, "skip_download": True, "no_warnings": True}
    )


class YtdlpFetcher(MetadataFetcher):
    name = "ytdlp"

    def __init__(self, ydl_factory=None):
        self._ydl_factory = ydl_factory or _default_factory

    def fetch(self, url: str, shortcode: str) -> ReelMetadata:
        try:
            with self._ydl_factory() as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:  # yt-dlp raises many error types
            raise FetchError(f"yt-dlp failed: {exc}") from exc
        return self._normalize(info or {}, url, shortcode)

    def _normalize(self, info: dict, url: str, shortcode: str) -> ReelMetadata:
        caption = info.get("description") or ""
        post_date = None
        if info.get("timestamp"):
            post_date = datetime.utcfromtimestamp(info["timestamp"]).date()
        elif info.get("upload_date"):
            post_date = datetime.strptime(info["upload_date"], "%Y%m%d").date()
        return ReelMetadata(
            shortcode=shortcode,
            url=url,
            caption=caption,
            hashtags=parse_hashtags(caption),
            author=info.get("uploader") or info.get("uploader_id") or "",
            post_date=post_date,
            source=self.name,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_ytdlp_fetcher.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add reel_categorizer/fetchers/ytdlp_fetcher.py tests/test_ytdlp_fetcher.py
git commit -m "feat: add yt-dlp metadata fetcher"
```

---

## Task 7: Apify fallback fetcher

**Files:**
- Create: `reel_categorizer/fetchers/apify_fetcher.py`
- Test: `tests/test_apify_fetcher.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

import pytest

from reel_categorizer.fetchers.apify_fetcher import ApifyFetcher
from reel_categorizer.fetchers.base import FetchError


class _Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _Http:
    def __init__(self, data):
        self._data = data
        self.calls = []

    def post(self, url, json=None):
        self.calls.append((url, json))
        return _Resp(self._data)


def test_apify_disabled_without_token():
    f = ApifyFetcher(token=None)
    with pytest.raises(FetchError):
        f.fetch("u", "abc")


def test_apify_normalizes_item():
    item = {"caption": "Gym day #fitness", "ownerUsername": "fit",
            "hashtags": ["Fitness"], "timestamp": "2026-02-03T10:00:00.000Z"}
    http = _Http([item])
    f = ApifyFetcher(token="tok", http=http)
    m = f.fetch("https://www.instagram.com/reel/abc/", "abc")
    assert m.author == "fit"
    assert m.hashtags == ["fitness"]
    assert m.post_date == date(2026, 2, 3)
    assert m.source == "apify"
    assert "tok" in http.calls[0][0]


def test_apify_empty_raises():
    f = ApifyFetcher(token="tok", http=_Http([]))
    with pytest.raises(FetchError):
        f.fetch("u", "abc")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_apify_fetcher.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`reel_categorizer/fetchers/apify_fetcher.py`:
```python
from __future__ import annotations

from datetime import datetime

import requests

from ..models import ReelMetadata
from .base import FetchError, MetadataFetcher, parse_hashtags

APIFY_ACTOR = "apify~instagram-scraper"


class ApifyFetcher(MetadataFetcher):
    name = "apify"

    def __init__(self, token: str | None, http=requests):
        self._token = token
        self._http = http

    def fetch(self, url: str, shortcode: str) -> ReelMetadata:
        if not self._token:
            raise FetchError("Apify token not configured")
        endpoint = (
            f"https://api.apify.com/v2/acts/{APIFY_ACTOR}"
            f"/run-sync-get-dataset-items?token={self._token}"
        )
        try:
            resp = self._http.post(
                endpoint, json={"directUrls": [url], "resultsLimit": 1}
            )
            resp.raise_for_status()
            items = resp.json()
        except Exception as exc:
            raise FetchError(f"Apify request failed: {exc}") from exc
        if not items:
            raise FetchError("Apify returned no items")
        return self._normalize(items[0], url, shortcode)

    def _normalize(self, item: dict, url: str, shortcode: str) -> ReelMetadata:
        caption = item.get("caption") or ""
        hashtags = [h.lower() for h in item.get("hashtags", [])]
        if not hashtags:
            hashtags = parse_hashtags(caption)
        post_date = None
        ts = item.get("timestamp")
        if isinstance(ts, str):
            try:
                post_date = datetime.fromisoformat(
                    ts.replace("Z", "+00:00")
                ).date()
            except ValueError:
                post_date = None
        return ReelMetadata(
            shortcode=shortcode,
            url=url,
            caption=caption,
            hashtags=hashtags,
            author=item.get("ownerUsername") or "",
            post_date=post_date,
            source=self.name,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_apify_fetcher.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add reel_categorizer/fetchers/apify_fetcher.py tests/test_apify_fetcher.py
git commit -m "feat: add Apify fallback fetcher"
```

---

## Task 8: Fetcher orchestration (`get_metadata`)

**Files:**
- Modify: `reel_categorizer/fetchers/__init__.py`
- Test: `tests/test_get_metadata.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from reel_categorizer.fetchers import get_metadata
from reel_categorizer.fetchers.base import MetadataFetcher, FetchError
from reel_categorizer.models import ReelMetadata


class _OK(MetadataFetcher):
    name = "ok"

    def fetch(self, url, shortcode):
        return ReelMetadata(shortcode=shortcode, url=url, source="ok")


class _Fail(MetadataFetcher):
    name = "fail"

    def fetch(self, url, shortcode):
        raise FetchError("nope")


def test_returns_first_success():
    assert get_metadata("u", "abc", [_OK()]).source == "ok"


def test_falls_back_on_failure():
    assert get_metadata("u", "abc", [_Fail(), _OK()]).source == "ok"


def test_all_fail_raises():
    with pytest.raises(FetchError):
        get_metadata("u", "abc", [_Fail(), _Fail()])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_get_metadata.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_metadata'`.

- [ ] **Step 3: Write minimal implementation**

`reel_categorizer/fetchers/__init__.py`:
```python
from __future__ import annotations

from ..models import ReelMetadata
from .base import FetchError, MetadataFetcher


def get_metadata(
    url: str, shortcode: str, fetchers: list[MetadataFetcher]
) -> ReelMetadata:
    errors = []
    for fetcher in fetchers:
        try:
            return fetcher.fetch(url, shortcode)
        except FetchError as exc:
            errors.append(f"{fetcher.name}: {exc}")
    raise FetchError("All fetchers failed -> " + " | ".join(errors))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_get_metadata.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add reel_categorizer/fetchers/__init__.py tests/test_get_metadata.py
git commit -m "feat: add fetcher fallback orchestration"
```

---

## Task 9: Classifier (Claude)

**Files:**
- Create: `reel_categorizer/classifier.py`
- Test: `tests/test_classifier.py`

> **Before writing the implementation:** invoke the `claude-api` skill to confirm the current Haiku model id, the `messages.create` signature, and how to read text out of the response (`message.content[0].text`). The code below reflects the expected shape; reconcile any differences the skill surfaces.

- [ ] **Step 1: Write the failing test**

```python
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


def test_parse_response_normalizes_tags():
    text = ('{"category":"Food Recipes","is_new_category":false,'
            '"tags":["High-Protein"," meal-prep "],"reason":"food"}')
    c = parse_response(text)
    assert c.category == "Food Recipes"
    assert c.is_new_category is False
    assert c.tags == ["high-protein", "meal-prep"]


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`reel_categorizer/classifier.py`:
```python
from __future__ import annotations

import json
from dataclasses import dataclass

from .models import ReelMetadata

MODEL = "claude-haiku-4-5-20251001"

SYSTEM = (
    "You are a precise content classifier for Instagram reels. "
    "You always respond with a single JSON object and nothing else."
)


@dataclass
class Classification:
    category: str
    is_new_category: bool
    tags: list[str]
    reason: str


def build_prompt(
    meta: ReelMetadata, categories: list[str], existing_tags: list[str]
) -> str:
    cat_lines = "\n".join(f"- {c}" for c in categories)
    vocab = ", ".join(existing_tags) if existing_tags else "(none yet)"
    hashtags = " ".join("#" + h for h in meta.hashtags)
    return (
        "Classify this Instagram reel.\n\n"
        "Categories (choose exactly one best fit):\n"
        f"{cat_lines}\n\n"
        "Existing tag vocabulary (REUSE a tag when it is semantically "
        "equivalent to one you'd otherwise create — prefer existing 'budget' "
        "over a new 'low-cost'):\n"
        f"{vocab}\n\n"
        "Reel:\n"
        f"Author: {meta.author}\n"
        f"Post date: {meta.post_date}\n"
        f"Hashtags: {hashtags}\n"
        f"Caption:\n{meta.caption}\n\n"
        "Respond with ONLY a JSON object with keys: "
        "category (string), is_new_category (boolean), "
        "tags (array of 3-6 lowercase kebab-case strings), reason (string). "
        "If no listed category fits well, set is_new_category true and put "
        "your proposed new category name in category."
    )


def _extract_json(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object found in response: {text!r}")
    return text[start:end + 1]


def parse_response(text: str) -> Classification:
    data = json.loads(_extract_json(text))
    tags = [t.strip().lower() for t in data.get("tags", []) if t and t.strip()]
    return Classification(
        category=str(data["category"]).strip(),
        is_new_category=bool(data["is_new_category"]),
        tags=tags,
        reason=str(data.get("reason", "")).strip(),
    )


class Classifier:
    def __init__(self, completion_fn):
        # completion_fn(system: str, prompt: str) -> str (model's text reply)
        self._complete = completion_fn

    def classify(
        self, meta: ReelMetadata, categories: list[str], existing_tags: list[str]
    ) -> Classification:
        prompt = build_prompt(meta, categories, existing_tags)
        return parse_response(self._complete(SYSTEM, prompt))


def anthropic_completion_fn(api_key: str):
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    def _complete(system: str, prompt: str) -> str:
        message = client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    return _complete
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_classifier.py -v`
Expected: PASS (4 tests). `anthropic_completion_fn` is not exercised by tests (no network); it is verified manually in Task 12.

- [ ] **Step 5: Commit**

```bash
git add reel_categorizer/classifier.py tests/test_classifier.py
git commit -m "feat: add Claude reel classifier"
```

---

## Task 10: Notion store

**Files:**
- Create: `reel_categorizer/notion_store.py`
- Test: `tests/test_notion_store.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import date

from reel_categorizer.models import ReelMetadata
from reel_categorizer.notion_store import NotionStore


class _FakeNotion:
    def __init__(self, db=None, query=None):
        self._db = db or {"properties": {"Tags": {"multi_select": {"options": [
            {"name": "budget"}, {"name": "quick"}]}}}}
        self._query = query or {"results": []}
        self.created = []
        self.databases = self._Databases(self)
        self.pages = self._Pages(self)

    class _Databases:
        def __init__(self, outer):
            self._o = outer

        def retrieve(self, database_id):
            return self._o._db

        def query(self, database_id, filter):
            return self._o._query

    class _Pages:
        def __init__(self, outer):
            self._o = outer

        def create(self, parent, properties):
            self._o.created.append(properties)
            return {"url": "https://notion.so/page"}


def test_existing_tags():
    assert NotionStore(_FakeNotion(), "db").existing_tags() == ["budget", "quick"]


def test_find_by_shortcode_none():
    assert NotionStore(_FakeNotion(query={"results": []}), "db").find_by_shortcode("a") is None


def test_find_by_shortcode_hit():
    q = {"results": [{"properties": {"Category": {"select": {"name": "Tech"}}}}]}
    assert NotionStore(_FakeNotion(query=q), "db").find_by_shortcode("a") == "Tech"


def test_create_entry_builds_props():
    fake = _FakeNotion()
    store = NotionStore(fake, "db")
    m = ReelMetadata(
        shortcode="abc", url="https://x/reel/abc/", caption="Tacos #food",
        hashtags=["food"], author="chef", post_date=date(2026, 1, 5))
    url = store.create_entry(m, "Food Places", ["tacos", "budget"])
    assert url == "https://notion.so/page"
    props = fake.created[0]
    assert props["Category"]["select"]["name"] == "Food Places"
    assert {"name": "tacos"} in props["Tags"]["multi_select"]
    assert props["Shortcode"]["rich_text"][0]["text"]["content"] == "abc"
    assert props["Post Date"]["date"]["start"] == "2026-01-05"


def test_create_entry_without_post_date_omits_property():
    fake = _FakeNotion()
    m = ReelMetadata(shortcode="abc", url="u", caption="hi", author="x")
    NotionStore(fake, "db").create_entry(m, "Tech", ["ai"])
    assert "Post Date" not in fake.created[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_notion_store.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`reel_categorizer/notion_store.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_notion_store.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add reel_categorizer/notion_store.py tests/test_notion_store.py
git commit -m "feat: add Notion store with dedupe and tag vocab"
```

---

## Task 11: Pipeline orchestration

**Files:**
- Create: `reel_categorizer/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
from reel_categorizer.pipeline import Pipeline
from reel_categorizer.models import ReelMetadata
from reel_categorizer.fetchers.base import MetadataFetcher, FetchError
from reel_categorizer.classifier import Classification


class _Fetcher(MetadataFetcher):
    name = "f"

    def __init__(self, meta=None, err=False):
        self._m = meta
        self._err = err

    def fetch(self, url, shortcode):
        if self._err:
            raise FetchError("x")
        return self._m or ReelMetadata(shortcode=shortcode, url=url, caption="cap")


class _Classifier:
    def __init__(self, result):
        self._r = result

    def classify(self, meta, cats, tags):
        return self._r


class _Store:
    def __init__(self, existing=None, tags=None):
        self._existing = existing
        self._tags = tags or []
        self.created = []

    def find_by_shortcode(self, sc):
        return self._existing

    def existing_tags(self):
        return self._tags

    def create_entry(self, meta, category, tags):
        self.created.append((category, tags))
        return "https://notion/p"


def _pipe(fetcher, classifier, store, cats=("Tech", "Food Recipes")):
    return Pipeline([fetcher], classifier, store, lambda: list(cats))


def test_invalid_url():
    r = _pipe(_Fetcher(), _Classifier(None), _Store()).process("https://example.com/x")
    assert r.kind == "invalid"


def test_duplicate():
    r = _pipe(_Fetcher(), _Classifier(None), _Store(existing="Tech")).process(
        "https://www.instagram.com/reel/abc/")
    assert r.kind == "duplicate"
    assert r.category == "Tech"


def test_fetch_error():
    r = _pipe(_Fetcher(err=True), _Classifier(None), _Store()).process(
        "https://www.instagram.com/reel/abc/")
    assert r.kind == "error"


def test_saved():
    c = Classification("Tech", False, ["ai"], "r")
    store = _Store()
    r = _pipe(_Fetcher(), _Classifier(c), store).process(
        "https://www.instagram.com/reel/abc/")
    assert r.kind == "saved"
    assert r.category == "Tech"
    assert store.created[0][0] == "Tech"


def test_needs_category_when_new():
    c = Classification("Cooking", True, ["tacos"], "r")
    store = _Store()
    r = _pipe(_Fetcher(), _Classifier(c), store).process(
        "https://www.instagram.com/reel/abc/")
    assert r.kind == "needs_category"
    assert r.proposed_category == "Cooking"
    assert r.tags == ["tacos"]
    assert store.created == []


def test_needs_category_when_unknown_category():
    c = Classification("Cooking", False, ["tacos"], "r")  # not in list
    store = _Store()
    r = _pipe(_Fetcher(), _Classifier(c), store).process(
        "https://www.instagram.com/reel/abc/")
    assert r.kind == "needs_category"


def test_save_persists():
    store = _Store()
    p = _pipe(_Fetcher(), _Classifier(None), store)
    out = p.save(ReelMetadata(shortcode="abc", url="u"), "Tech", ["ai"])
    assert out == "https://notion/p"
    assert store.created[0] == ("Tech", ["ai"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`reel_categorizer/pipeline.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field

from .classifier import Classification
from .fetchers import get_metadata
from .fetchers.base import FetchError
from .models import ReelMetadata
from .urls import InvalidReelURL, canonical_url, extract_shortcode


@dataclass
class ProcessResult:
    kind: str  # invalid | duplicate | error | needs_category | saved
    message: str
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    proposed_category: str | None = None
    meta: ReelMetadata | None = None


class Pipeline:
    def __init__(self, fetchers, classifier, store, load_categories):
        self.fetchers = fetchers
        self.classifier = classifier
        self.store = store
        self.load_categories = load_categories

    def process(self, url: str) -> ProcessResult:
        try:
            shortcode = extract_shortcode(url)
        except InvalidReelURL:
            return ProcessResult(
                "invalid", "That doesn't look like an Instagram reel link."
            )

        existing = self.store.find_by_shortcode(shortcode)
        if existing:
            return ProcessResult(
                "duplicate", f"Already saved under {existing}.", category=existing
            )

        try:
            meta = get_metadata(canonical_url(shortcode), shortcode, self.fetchers)
        except FetchError as exc:
            return ProcessResult("error", f"Couldn't fetch that reel ({exc}).")

        categories = self.load_categories()
        try:
            existing_tags = self.store.existing_tags()
            result = self.classifier.classify(meta, categories, existing_tags)
        except Exception as exc:  # noqa: BLE001 - surface any classify failure
            return ProcessResult("error", f"Classification failed ({exc}).")

        if result.is_new_category or result.category not in categories:
            return ProcessResult(
                "needs_category",
                f"No existing category fits — I'd suggest “{result.category}”.",
                proposed_category=result.category,
                tags=result.tags,
                meta=meta,
            )

        self.store.create_entry(meta, result.category, result.tags)
        return ProcessResult(
            "saved", f"Saved to {result.category}.",
            category=result.category, tags=result.tags, meta=meta,
        )

    def save(self, meta: ReelMetadata, category: str, tags: list[str]) -> str:
        return self.store.create_entry(meta, category, tags)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add reel_categorizer/pipeline.py tests/test_pipeline.py
git commit -m "feat: add orchestration pipeline"
```

---

## Task 12: Telegram bot glue + entrypoint

**Files:**
- Create: `reel_categorizer/bot.py`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write the failing test (pure URL extraction helper)**

```python
from reel_categorizer.bot import extract_urls


def test_extract_urls_finds_links():
    text = "check https://www.instagram.com/reel/abc/ and https://x.com/y"
    assert extract_urls(text) == [
        "https://www.instagram.com/reel/abc/", "https://x.com/y"]


def test_extract_urls_none():
    assert extract_urls("just text") == []
    assert extract_urls(None) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_bot.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`reel_categorizer/bot.py`:
```python
from __future__ import annotations

import re
import uuid

from notion_client import Client as NotionClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .classifier import Classifier, anthropic_completion_fn
from .config import add_category, load_categories, load_settings
from .fetchers.apify_fetcher import ApifyFetcher
from .fetchers.ytdlp_fetcher import YtdlpFetcher
from .notion_store import NotionStore
from .pipeline import Pipeline

_URL_RE = re.compile(r"https?://\S+")

HELP = (
    "Send me an Instagram reel link and I'll file it in Notion.\n"
    "I pick a category and add searchable tags automatically."
)


def extract_urls(text: str | None) -> list[str]:
    return _URL_RE.findall(text or "")


def build_pipeline(settings) -> Pipeline:
    fetchers = [YtdlpFetcher(), ApifyFetcher(settings.apify_token)]
    classifier = Classifier(anthropic_completion_fn(settings.anthropic_api_key))
    store = NotionStore(
        NotionClient(auth=settings.notion_token), settings.notion_database_id
    )
    return Pipeline(fetchers, classifier, store, load_categories)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    urls = [u for u in extract_urls(update.message.text) if "instagram.com" in u]
    if not urls:
        await update.message.reply_text("Send me an Instagram reel link.")
        return
    pipeline: Pipeline = context.application.bot_data["pipeline"]
    for url in urls:
        result = pipeline.process(url)
        if result.kind == "needs_category":
            token = uuid.uuid4().hex[:8]
            context.application.bot_data.setdefault("pending", {})[token] = (
                result.meta, result.tags, result.proposed_category)
            categories = load_categories()
            keyboard = [[InlineKeyboardButton(
                f'Add "{result.proposed_category}" & file',
                callback_data=f"add:{token}")]]
            keyboard += [
                [InlineKeyboardButton(c, callback_data=f"pick:{token}:{i}")]
                for i, c in enumerate(categories)
            ]
            keyboard.append([InlineKeyboardButton(
                "Skip (Uncategorized)", callback_data=f"skip:{token}")])
            await update.message.reply_text(
                f"{result.message}\nChoose a category:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            suffix = (" · tags: " + ", ".join(result.tags)) if result.tags else ""
            await update.message.reply_text(result.message + suffix)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    pipeline: Pipeline = context.application.bot_data["pipeline"]
    pending = context.application.bot_data.get("pending", {})
    parts = query.data.split(":")
    action, token = parts[0], parts[1]
    entry = pending.get(token)
    if not entry:
        await query.edit_message_text("That request expired — send the link again.")
        return
    meta, tags, proposed = entry
    if action == "add":
        add_category(proposed)
        pipeline.save(meta, proposed, tags)
        await query.edit_message_text(f"Added category “{proposed}” and saved.")
    elif action == "pick":
        category = load_categories()[int(parts[2])]
        pipeline.save(meta, category, tags)
        await query.edit_message_text(f"Saved to {category}.")
    else:  # skip
        pipeline.save(meta, "Uncategorized", tags)
        await query.edit_message_text("Saved to Uncategorized.")
    pending.pop(token, None)


def main() -> None:
    settings = load_settings()
    app = Application.builder().token(settings.telegram_token).build()
    app.bot_data["pipeline"] = build_pipeline(settings)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_bot.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: all tests PASS.

- [ ] **Step 6: Manual smoke test (requires real credentials + Notion DB from Task 13)**

Prerequisite: complete Task 13's Notion setup and fill `.env`. Then run:
```bash
.venv/Scripts/python -m reel_categorizer.bot
```
In Telegram, send `/start`, then a real reel link. Verify: bot replies with a category + tags, and a row appears in the Notion database. Send the same link again → expect "Already saved under …". Send a clearly off-list reel → expect the new-category buttons.

- [ ] **Step 7: Commit**

```bash
git add reel_categorizer/bot.py tests/test_bot.py
git commit -m "feat: add Telegram bot and entrypoint"
```

---

## Task 13: README and Notion setup docs

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

````markdown
# Instagram Reel Categorizer

A personal Telegram bot: send it an Instagram reel link and it classifies the
reel and files it as a row in a Notion database with searchable tags.

## Setup

### 1. Install
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux
```

### 2. Create the Notion database
Create a new database (full page) with these properties — names and types must
match exactly:

| Property | Type |
|----------|------|
| Title | Title |
| Category | Select |
| Tags | Multi-select |
| Caption | Text |
| Hashtags | Text |
| Author | Text |
| Post Date | Date |
| Reel URL | URL |
| Shortcode | Text |
| Date Added | Created time |

(Seed a couple of `Category` options if you like — new ones are auto-added.)

### 3. Create a Notion integration
1. Go to https://www.notion.so/my-integrations → New integration → copy the
   **Internal Integration Token** → that's `NOTION_TOKEN`.
2. Open your database page → `•••` menu → **Connections** → add your integration.
3. `NOTION_DATABASE_ID` is the 32-char id in the database URL:
   `notion.so/<workspace>/<DATABASE_ID>?v=...`.

### 4. Create the Telegram bot
Message **@BotFather** → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`.

### 5. Anthropic + optional Apify
- `ANTHROPIC_API_KEY` from the Anthropic console.
- `APIFY_TOKEN` (optional) enables the paid fallback when yt-dlp is blocked.

### 6. Configure
```bash
cp .env.example .env   # then fill in the values
```
Edit `categories.json` to taste.

## Run
```bash
.venv/Scripts/python -m reel_categorizer.bot
```
Leave it running (the bot only works while this process is up). Send a reel link
in Telegram.

## Test
```bash
.venv/Scripts/python -m pytest -q
```

## How it works
URL → shortcode → dedupe check → fetch metadata (yt-dlp, Apify fallback) →
Claude classifies (category + tags, reusing existing tag vocabulary) → Notion row.
New categories require a tap-to-confirm; tags are added automatically.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add setup and usage README"
```

---

## Self-Review

**Spec coverage:**
- Telegram bot, long-polling → Task 12. ✓
- Notion destination + schema → Tasks 10, 13. ✓
- Text-metadata-only fetch, swappable, free-first/paid-fallback → Tasks 5–8. ✓
- Fixed categories + suggest-new with approval → Tasks 4, 11, 12. ✓
- Automatic tags + vocabulary reuse for canonicalization → Tasks 9, 10, 11. ✓
- Dedupe by shortcode → Tasks 10, 11. ✓
- Error handling (invalid/fetch-fail/classify-fail) → Task 11. ✓
- TDD with mocked externals → every task. ✓
- Extensible toward frames/audio → `ReelMetadata` + fetcher interface leave room. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `ReelMetadata`, `Classification(category, is_new_category, tags, reason)`, `ProcessResult(kind, message, category, tags, proposed_category, meta)`, `get_metadata(url, shortcode, fetchers)`, `MetadataFetcher.fetch(url, shortcode)`, `NotionStore.{existing_tags, find_by_shortcode, create_entry}`, `Pipeline.{process, save}` — names match across all tasks. ✓

**Deferred (per spec non-goals):** video frames/audio, `tag_aliases.json`, cloud hosting — intentionally not in this plan.
