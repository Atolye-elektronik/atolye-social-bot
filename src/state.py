"""Hangi postun nereye paylaşıldığını hatırlar, böylece aynı post iki kez atılmaz."""

from __future__ import annotations

import datetime as dt
import json
import pathlib

STATE_PATH = pathlib.Path("state/published.json")


def load() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save(data: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def already_published(data: dict, slug: str, platform: str) -> bool:
    return platform in data.get(slug, {})


def mark_published(data: dict, slug: str, platform: str, result_id: str) -> None:
    data.setdefault(slug, {})[platform] = {
        "id": result_id,
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
