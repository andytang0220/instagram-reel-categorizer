from __future__ import annotations

import json
from dataclasses import dataclass

from .models import ReelMetadata

MODEL = "claude-haiku-4-5"

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
