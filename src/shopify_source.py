"""Shopify ürünlerinden otomatik post taslağı üretir.

Mağazanın herkese açık ürün listesini kullanır (products.json), bu yüzden
hiçbir API anahtarı ya da token gerekmiyor.

Kullanımı:
    python -m src.shopify_source --count 3
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re

import requests

from . import config

STORE_URL = os.environ.get("STORE_URL", "https://atolyeelektronik.com").rstrip("/")
STATE_PATH = pathlib.Path("state/shopify_seen.json")
POSTS_DIR = pathlib.Path("posts")


def _slugify(text: str) -> str:
    replacements = {
        "ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:60] or "urun"


def _strip_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def ozet(raw: str, limit: int = 220) -> str:
    """Aciklamayi cumle/kelime sinirinda keser; yarim kelime birakmaz."""
    text = _strip_html(raw)
    if len(text) <= limit:
        return text
    kesit = text[:limit]
    # once cumle sonu ara
    for nokta in (". ", "! ", "? "):
        yer = kesit.rfind(nokta)
        if yer > limit * 0.5:
            return kesit[:yer + 1].strip()
    # yoksa son bosluktan kes
    yer = kesit.rfind(" ")
    if yer > 0:
        kesit = kesit[:yer]
    return kesit.rstrip(" ,;:-") + "..."


def _load_seen() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        return set(json.loads(STATE_PATH.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return set()


def _save_seen(seen: set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def fetch_products(limit: int = 250) -> list[dict]:
    response = requests.get(
        f"{STORE_URL}/products.json",
        params={"limit": limit},
        headers={"User-Agent": "atolye-social-bot"},
        timeout=60,
    )
    response.raise_for_status()
    return response.json().get("products", [])


def build_caption(product: dict) -> str:
    title = product.get("title", "").strip()
    description = ozet(product.get("body_html", ""))

    lines = [f"\u26a1 {title}"]
    if description:
        lines += ["", description]
    if product.get("handle"):
        lines += ["", f"Detaylar ve siparis \U0001f449 {STORE_URL}/products/{product['handle']}"]
    lines += ["", "#atolyeelektronik #elektronik #maker #hobi #antalya"]
    return "\n".join(lines)


def generate(count: int = 3, start_in_hours: int = 24, spacing_hours: int = 24) -> list[pathlib.Path]:
    seen = _load_seen()
    products = fetch_products()

    fresh = [
        p for p in products
        if str(p.get("id")) not in seen and (p.get("images") or [])
    ]
    if not fresh:
        print("Yeni post üretilecek ürün bulunamadı.")
        return []

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    created: list[pathlib.Path] = []
    when = dt.datetime.now().astimezone() + dt.timedelta(hours=start_in_hours)

    for product in fresh[:count]:
        slug = f"{when:%Y-%m-%d}-{_slugify(product.get('handle') or product.get('title', ''))}"
        path = POSTS_DIR / f"{slug}.md"
        if path.exists():
            when += dt.timedelta(hours=spacing_hours)
            continue

        image_url = product["images"][0]["src"]
        body = (
            "---\n"
            f"platforms: [{', '.join(config.DEFAULT_PLATFORMS)}]\n"
            f"media: {image_url}\n"
            f"publish_at: {when:%Y-%m-%d %H:%M}\n"
            "---\n"
            f"{build_caption(product)}\n"
        )
        path.write_text(body, encoding="utf-8")
        created.append(path)
        seen.add(str(product["id"]))
        when += dt.timedelta(hours=spacing_hours)
        print(f"Oluşturuldu: {path}")

    _save_seen(seen)
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Shopify ürünlerinden post taslağı üret")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--start-in-hours", type=int, default=24)
    parser.add_argument("--spacing-hours", type=int, default=24)
    args = parser.parse_args()
    generate(args.count, args.start_in_hours, args.spacing_hours)


if __name__ == "__main__":
    main()
