"""Shopify ürünlerinden otomatik post taslağı üretir.

Kullanımı:
    python -m src.shopify_source --count 3

Her çalışmada, daha önce post üretilmemiş ürünlerden seçip
posts/ klasörüne yeni markdown dosyaları yazar. Dosyaları
paylaşılmadan önce elden geçirebilirsin — metinleri düzenle,
tarihini ayarla, sonra commit et.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re

import requests

from . import config

STATE_PATH = pathlib.Path("state/shopify_seen.json")
POSTS_DIR = pathlib.Path("posts")

QUERY = """
query Products($first: Int!) {
  products(first: $first, sortKey: CREATED_AT, reverse: true) {
    edges {
      node {
        id
        title
        handle
        onlineStoreUrl
        description
        featuredImage { url }
        priceRangeV2 { minVariantPrice { amount currencyCode } }
      }
    }
  }
}
"""


def _slugify(text: str) -> str:
    replacements = {
        "ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:60] or "urun"


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


def fetch_products(limit: int = 20) -> list[dict]:
    if not (config.SHOPIFY_STORE and config.SHOPIFY_TOKEN):
        raise RuntimeError("SHOPIFY_STORE ve SHOPIFY_ADMIN_TOKEN tanımlı değil.")

    url = (
        f"https://{config.SHOPIFY_STORE}.myshopify.com"
        f"/admin/api/{config.SHOPIFY_API_VERSION}/graphql.json"
    )
    response = requests.post(
        url,
        headers={
            "X-Shopify-Access-Token": config.SHOPIFY_TOKEN,
            "Content-Type": "application/json",
        },
        json={"query": QUERY, "variables": {"first": limit}},
        timeout=60,
    )
    payload = response.json()
    if "errors" in payload:
        raise RuntimeError(f"Shopify hatası: {payload['errors']}")
    return [edge["node"] for edge in payload["data"]["products"]["edges"]]


def build_caption(product: dict) -> str:
    title = product["title"]
    price = (product.get("priceRangeV2") or {}).get("minVariantPrice") or {}
    amount = price.get("amount")
    currency = price.get("currencyCode", "TRY")

    description = (product.get("description") or "").strip()
    description = re.sub(r"\s+", " ", description)[:180]

    lines = [f"⚡ {title}"]
    if description:
        lines.append("")
        lines.append(description)
    if amount:
        try:
            pretty = f"{float(amount):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except (TypeError, ValueError):
            pretty = str(amount)
        lines.append("")
        lines.append(f"Fiyat: {pretty} {currency}")
    if product.get("onlineStoreUrl"):
        lines.append(product["onlineStoreUrl"])
    lines.append("")
    lines.append("#atolyeelektronik #elektronik #maker #arduino #hobi")
    return "\n".join(lines)


def generate(count: int = 3, start_in_hours: int = 24, spacing_hours: int = 24) -> list[pathlib.Path]:
    seen = _load_seen()
    products = fetch_products(limit=50)

    fresh = [p for p in products if p["id"] not in seen and (p.get("featuredImage") or {}).get("url")]
    if not fresh:
        print("Yeni post üretilecek ürün bulunamadı.")
        return []

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    created = []
    when = dt.datetime.now(dt.timezone.utc).astimezone() + dt.timedelta(hours=start_in_hours)

    for product in fresh[:count]:
        slug = f"{when:%Y-%m-%d}-{_slugify(product['handle'] or product['title'])}"
        path = POSTS_DIR / f"{slug}.md"
        if path.exists():
            when += dt.timedelta(hours=spacing_hours)
            continue

        image_url = product["featuredImage"]["url"]
        body = (
            "---\n"
            "platforms: [instagram, facebook]\n"
            f"media: {image_url}\n"
            f"publish_at: {when:%Y-%m-%d %H:%M}\n"
            "---\n"
            f"{build_caption(product)}\n"
        )
        path.write_text(body, encoding="utf-8")
        created.append(path)
        seen.add(product["id"])
        when += dt.timedelta(hours=spacing_hours)
        print(f"Oluşturuldu: {path}")

    _save_seen(seen)
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Shopify ürünlerinden post taslağı üret")
    parser.add_argument("--count", type=int, default=3, help="Kaç post üretilsin")
    parser.add_argument("--start-in-hours", type=int, default=24)
    parser.add_argument("--spacing-hours", type=int, default=24)
    args = parser.parse_args()
    generate(args.count, args.start_in_hours, args.spacing_hours)


if __name__ == "__main__":
    main()
