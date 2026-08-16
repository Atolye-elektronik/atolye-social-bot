"""posts/ klasöründeki markdown post dosyalarını okur.

Bir post dosyası şöyle görünür:

    ---
    platforms: [instagram, facebook]
    media: posts/media/urun1.jpg
    publish_at: 2026-08-01 10:00
    ---
    Buraya paylaşım metni gelir.
    Birden fazla satır olabilir. #atolyeelektronik

`publish_at` boş bırakılırsa post ilk çalışmada paylaşılır.
Saat dilimi Europe/Istanbul kabul edilir.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import re
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Istanbul")
POSTS_DIR = pathlib.Path("posts")

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


@dataclass
class Post:
    slug: str
    path: pathlib.Path
    platforms: list[str]
    caption: str
    media: str | list[str] | None = None
    publish_at: dt.datetime | None = None
    extra: dict = field(default_factory=dict)

    @property
    def is_carousel(self) -> bool:
        return isinstance(self.media, list) and len(self.media) > 1

    @property
    def media_list(self) -> list[str]:
        if not self.media:
            return []
        if isinstance(self.media, list):
            return self.media
        return [self.media]

    @property
    def is_video(self) -> bool:
        if not self.media or isinstance(self.media, list):
            return False
        return self.media.lower().endswith((".mp4", ".mov", ".m4v"))

    def is_due(self, now: dt.datetime | None = None) -> bool:
        if self.publish_at is None:
            return True
        now = now or dt.datetime.now(TZ)
        return self.publish_at <= now


def _parse_scalar(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
    return raw.strip("'\"")


def _parse_front_matter(text: str) -> dict:
    data: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = _parse_scalar(value)
    return data


def parse_datetime(raw) -> dt.datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            parsed = dt.datetime.strptime(raw, fmt)
            return parsed.replace(tzinfo=TZ)
        except ValueError:
            continue
    raise ValueError(f"publish_at okunamadı: {raw!r} (beklenen biçim: 2026-08-01 10:00)")


def load_post(path: pathlib.Path) -> Post:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        raise ValueError(
            f"{path} dosyasında front matter bulunamadı. "
            "Dosya '---' satırıyla başlamalı."
        )

    meta = _parse_front_matter(match.group(1))
    caption = match.group(2).strip()

    platforms = meta.get("platforms") or ["instagram", "facebook"]
    if isinstance(platforms, str):
        platforms = [platforms]
    platforms = [p.strip().lower() for p in platforms]

    media = meta.get("media") or None
    if isinstance(media, list) and len(media) == 1:
        media = media[0]

    return Post(
        slug=path.stem,
        path=path,
        platforms=platforms,
        caption=caption,
        media=media,
        publish_at=parse_datetime(meta.get("publish_at")),
        extra=meta,
    )


def load_all(directory: pathlib.Path = POSTS_DIR) -> list[Post]:
    if not directory.exists():
        return []
    found = []
    for path in sorted(directory.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        found.append(load_post(path))
    return found
