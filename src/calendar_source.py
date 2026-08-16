"""Icerik takvimine gore ileriye donuk post taslaklari uretir.

`content/takvim.json` dosyasindaki haftalik slotlari okur, onumuzdeki N gun
icin hangi gun/saatte hangi temada post olmasi gerektigini hesaplar ve
Shopify urunlerinden birer taslak olusturur.

Kullanimi:
    python -m src.calendar_source --days 7
    python -m src.calendar_source --days 14 --dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
from zoneinfo import ZoneInfo

from . import config, gorsel, shopify_source

TZ = ZoneInfo("Europe/Istanbul")
CALENDAR_PATH = pathlib.Path("content/takvim.json")
POSTS_DIR = pathlib.Path("posts")

GUNLER = {
    "pazartesi": 0,
    "sali": 1,
    "carsamba": 2,
    "persembe": 3,
    "cuma": 4,
    "cumartesi": 5,
    "pazar": 6,
}


def load_calendar(path: pathlib.Path = CALENDAR_PATH) -> dict:
    if not path.exists():
        raise SystemExit(f"Takvim dosyasi bulunamadi: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _slot_datetimes(slotlar: list[dict], days: int, start: dt.date) -> list[tuple[dt.datetime, dict]]:
    """Onumuzdeki `days` gun icin (zaman, slot) ciftlerini sirali dondurur."""
    found: list[tuple[dt.datetime, dict]] = []
    for offset in range(days):
        day = start + dt.timedelta(days=offset)
        for slot in slotlar:
            gun = str(slot.get("gun", "")).strip().lower()
            if GUNLER.get(gun) != day.weekday():
                continue
            hour, _, minute = str(slot.get("saat", "11:00")).partition(":")
            when = dt.datetime(
                day.year, day.month, day.day,
                int(hour or 11), int(minute or 0), tzinfo=TZ,
            )
            found.append((when, slot))
    found.sort(key=lambda pair: pair[0])
    return found


def _pick(options, index: int) -> str:
    if isinstance(options, str):
        return options
    if not options:
        return ""
    return options[index % len(options)]


def build_caption(tema: dict, product: dict, index: int) -> str:
    title = (product.get("title") or "").strip()
    desc = shopify_source.ozet(product.get("body_html", ""))
    handle = product.get("handle") or ""
    url = f"{shopify_source.STORE_URL}/products/{handle}" if handle else shopify_source.STORE_URL

    fields = {"title": title, "desc": desc, "url": url}

    parts = [
        _pick(tema.get("basliklar"), index),
        "",
        _pick(tema.get("govde"), index),
        "",
        _pick(tema.get("kapanis"), index),
        "",
        tema.get("etiketler", ""),
    ]
    text = "\n".join(p for p in parts if p is not None)
    for key, value in fields.items():
        text = text.replace("{" + key + "}", value)
    # Bos alanlardan dogan fazla bos satirlari toparla.
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()


def generate(days: int = 7, dry_run: bool = False) -> list[pathlib.Path]:
    plan = load_calendar()
    slotlar = plan.get("slotlar") or []
    temalar = plan.get("temalar") or {}
    if not slotlar:
        print("Takvimde slot yok.")
        return []

    products = [p for p in shopify_source.fetch_products() if (p.get("images") or [])]
    if not products:
        print("Gorseli olan urun bulunamadi.")
        return []

    seen = shopify_source._load_seen()
    # Once hic kullanilmamis urunler, sonra bastan dolasilir.
    fresh = [p for p in products if str(p.get("id")) not in seen]
    havuz = fresh + [p for p in products if p not in fresh]

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    created: list[pathlib.Path] = []
    now = dt.datetime.now(TZ)
    start = now.date()

    index = 0
    for when, slot in _slot_datetimes(slotlar, days, start):
        if when <= now:
            continue

        tema_adi = str(slot.get("tema", "urun_tanitim"))
        tema = temalar.get(tema_adi)
        if tema is None:
            print(f"⚠️  Bilinmeyen tema: {tema_adi}")
            continue

        product = havuz[index % len(havuz)]
        slug = f"{when:%Y-%m-%d}-{tema_adi}-{shopify_source._slugify(product.get('handle') or product.get('title', ''))}"
        path = POSTS_DIR / f"{slug}.md"
        index += 1
        if path.exists():
            continue

        platforms = slot.get("platforms") or config.DEFAULT_PLATFORMS

        # Instagram 4:5 kabul ediyor, profil izgarasi 3:4 gosteriyor.
        # Ham urun fotograflari 3:2 yatay oldugu icin once 1080x1350
        # kareye TAM SIGDIRIP kaydediyoruz; boylece hicbir yerde kirpilmiyor.
        gorsel_yolu = pathlib.Path("posts/media") / f"{slug}.jpg"
        if not dry_run and not gorsel_yolu.exists():
            gorsel.kare_yap(product["images"][0]["src"],
                            product.get("title", ""), gorsel_yolu)

        body = (
            "---\n"
            f"platforms: [{', '.join(platforms)}]\n"
            f"media: {gorsel_yolu.as_posix()}\n"
            f"publish_at: {when:%Y-%m-%d %H:%M}\n"
            f"tema: {tema_adi}\n"
            "---\n"
            f"{build_caption(tema, product, index)}\n"
        )

        if dry_run:
            print(f"[DRY RUN] {path}  ({when:%d.%m.%Y %H:%M} · {tema_adi})")
        else:
            path.write_text(body, encoding="utf-8")
            seen.add(str(product["id"]))
            print(f"Olusturuldu: {path}  ({when:%d.%m.%Y %H:%M} · {tema_adi})")
        created.append(path)

    if created and not dry_run:
        shopify_source._save_seen(seen)
    if not created:
        print("Uretilecek yeni slot yok.")
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Icerik takviminden post taslagi uret")
    parser.add_argument("--days", type=int, default=7, help="Kac gun ileri bakilsin")
    parser.add_argument("--dry-run", action="store_true", help="Dosya yazma, sadece goster")
    args = parser.parse_args()
    generate(days=args.days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
