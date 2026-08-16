"""Shopify ürünlerinden Instagram/Facebook carousel taslağı üretir.

Mağazanın herkese açık ürün listesini (products.json) kullanır; ürünün
fotoğraflarından marka stilinde slide'lar oluşturur:

    kapak (ürün adı) → ürün fotoğrafları → kapanış (sipariş çağrısı)

Slide görselleri posts/media/carousel/<slug>/ klasörüne, post dosyası
posts/ klasörüne yazılır. Hangi ürün için carousel üretildiği
state/carousel_seen.json dosyasında tutulur — aynı ürün tekrarlanmaz.

Kullanımı:
    python -m src.carousel_source --count 2
    python -m src.carousel_source --handle temel-elektronik-deney-seti
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib

from . import carousel_gorsel, config
from .shopify_source import STORE_URL, _slugify, fetch_products, ozet

STATE_PATH = pathlib.Path("state/carousel_seen.json")
POSTS_DIR = pathlib.Path("posts")
MEDIA_DIR = pathlib.Path("posts/media/carousel")

MAX_SLIDE = 10          # Instagram carousel siniri
MIN_FOTO = 2            # tek fotolu urunler icin normal post yeterli


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


def build_caption(product: dict) -> str:
    title = product.get("title", "").strip()
    description = ozet(product.get("body_html", ""))

    lines = [f"\U0001f4f8 {title}", "", "Tüm detaylar için kaydır ➡️"]
    if description:
        lines += ["", description]
    if product.get("handle"):
        lines += ["", f"Sipariş için \U0001f449 {STORE_URL}/products/{product['handle']}"]
    lines += ["", "\U0001f381 İlk alışverişine özel: ATOLYE10 koduyla sepette %10 indirim!"]
    lines += ["", "#atolyeelektronik #elektronik #arduino #maker #hobi #antalya"]
    return "\n".join(lines)


def build_slides(product: dict, slug: str) -> list[str]:
    """Kapak + ürün fotoğrafları + kapanış slide'larını üretir, yolları döndürür."""
    klasor = MEDIA_DIR / slug
    title = product.get("title", "").strip()
    images = [img["src"] for img in product.get("images", [])]
    images = images[: MAX_SLIDE - 2]  # kapak ve kapanışa yer kalsın

    yollar: list[str] = []

    yol = klasor / "01-kapak.jpg"
    carousel_gorsel.kapak(title, yol)
    yollar.append(str(yol))

    for i, src in enumerate(images, start=1):
        yol = klasor / f"{i + 1:02d}-urun.jpg"
        carousel_gorsel.urun(src, title, sira=i, toplam=len(images), cikti=yol)
        yollar.append(str(yol))

    yol = klasor / f"{len(images) + 2:02d}-kapanis.jpg"
    carousel_gorsel.kapanis(yol)
    yollar.append(str(yol))

    return yollar


def write_post(product: dict, slug: str, slides: list[str], when: dt.datetime) -> pathlib.Path:
    path = POSTS_DIR / f"{slug}.md"
    media = "[" + ", ".join(slides) + "]"
    body = (
        "---\n"
        f"platforms: [{', '.join(config.DEFAULT_PLATFORMS)}]\n"
        f"media: {media}\n"
        f"publish_at: {when:%Y-%m-%d %H:%M}\n"
        "---\n"
        f"{build_caption(product)}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def generate(count: int = 2, start_in_hours: int = 24, spacing_hours: int = 48,
             handle: str | None = None) -> list[pathlib.Path]:
    seen = _load_seen()
    products = fetch_products()

    if handle:
        secilen = [p for p in products if p.get("handle") == handle]
        if not secilen:
            print(f"Ürün bulunamadı: {handle}")
            return []
    else:
        secilen = [
            p for p in products
            if str(p.get("id")) not in seen and len(p.get("images") or []) >= MIN_FOTO
        ]
        # once cok fotografli (carousel'e en uygun) urunler
        secilen.sort(key=lambda p: len(p.get("images") or []), reverse=True)

    if not secilen:
        print("Carousel üretilecek yeni ürün bulunamadı.")
        return []

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    created: list[pathlib.Path] = []
    when = dt.datetime.now().astimezone() + dt.timedelta(hours=start_in_hours)

    for product in secilen[:count]:
        slug = f"{when:%Y-%m-%d}-carousel-{_slugify(product.get('handle') or product.get('title', ''))}"
        path = POSTS_DIR / f"{slug}.md"
        if path.exists():
            when += dt.timedelta(hours=spacing_hours)
            continue

        print(f"Slide'lar üretiliyor: {product.get('title')}")
        slides = build_slides(product, slug)
        path = write_post(product, slug, slides, when)
        created.append(path)
        seen.add(str(product["id"]))
        when += dt.timedelta(hours=spacing_hours)
        print(f"Oluşturuldu: {path} ({len(slides)} slide)")

    _save_seen(seen)
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Shopify ürünlerinden carousel taslağı üret")
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--start-in-hours", type=int, default=24)
    parser.add_argument("--spacing-hours", type=int, default=48)
    parser.add_argument("--handle", help="Sadece bu ürün için üret (Shopify handle)")
    args = parser.parse_args()
    generate(args.count, args.start_in_hours, args.spacing_hours, handle=args.handle)


if __name__ == "__main__":
    main()
