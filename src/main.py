"""Zamanı gelmiş postları bulur ve ilgili platformlara paylaşır.

    python -m src.main            # zamanı gelenleri paylaş
    python -m src.main --dry-run  # hiçbir şey paylaşmadan ne olacağını göster
    python -m src.main --only 2026-08-01-urun   # tek bir postu işle
"""

from __future__ import annotations

import argparse
import inspect
import os
import sys

from . import (
    config,
    facebook,
    hikaye_gorsel,
    instagram,
    pinterest,
    pinterest_studio,
    posts,
    state,
    threads,
    tiktok,
    tiktok_studio,
    youtube,
)

PUBLISHERS = {
    "instagram": instagram.publish,
    "facebook": facebook.publish,
    "threads": threads.publish,
    # tiktok        → resmî API; denetimden geçmemiş uygulamada taslak bırakır
    # tiktok_studio → Studio arayüzü; doğrudan yayınlar, ileri tarihe zamanlar
    "tiktok": tiktok.publish,
    "tiktok_studio": tiktok_studio.publish,
    "youtube": youtube.publish,
    # pinterest        → resmî API; işletme hesabı + onaylı app ister
    # pinterest_studio → arayüz otomasyonu; kişisel hesapla çerezle pin atar
    "pinterest": pinterest.publish,
    "pinterest_studio": pinterest_studio.publish,
}


# pinterest_studio carousel postu kabul eder ama arayüzde karusel pin yok —
# ilk görseli tek pin olarak atar.
CAROUSEL_PLATFORMS = {"instagram", "facebook", "threads", "pinterest", "pinterest_studio"}

# publish isinin denemeyecegi platformlar (virgullu liste). tiktok_studio
# Playwright imaji isteyen tiktok-zamanla isinde yayinlanir; slim imajdaki
# publish denemesin diye CI'da SKIP_PLATFORMS=tiktok_studio veriliyor.
SKIP_PLATFORMS = {
    x.strip().lower()
    for x in os.environ.get("SKIP_PLATFORMS", "").split(",")
    if x.strip()
}


def _call(publisher, post):
    """Yayıncıyı çağırır; 'extra' parametresi destekliyorsa onu da geçirir."""
    params = inspect.signature(publisher).parameters
    if "extra" in params:
        return publisher(post.caption, post.media, post.is_video, extra=post.extra)
    return publisher(post.caption, post.media, post.is_video)


def _hikaye_bekliyor(post, published_state) -> bool:
    """IG feed postu son 24 saatte paylasildi ama hikayesi henuz gitmedi mi."""
    import datetime as _dt
    if not config.IG_STORY_AUTO:
        return False
    if state.already_published(published_state, post.slug, "instagram_story"):
        return False
    kayit = published_state.get(post.slug, {}).get("instagram") or {}
    try:
        zaman = _dt.datetime.fromisoformat(str(kayit.get("at")))
    except (TypeError, ValueError):
        return False
    return _dt.datetime.now(_dt.timezone.utc) - zaman < _dt.timedelta(hours=24)


def _hikaye_dene(post, published_state) -> None:
    if not config.IG_STORY_AUTO or state.already_published(published_state, post.slug, "instagram_story"):
        return
    print(f"→ {post.slug} → instagram hikaye")
    try:
        # Feed gorseli 4:5, hikaye 9:16. Ham gorseli hikayeye verince
        # Instagram saga-sola KIRPIYOR; 9:16 surumunu uretip onu atiyoruz.
        ham = post.media[0] if isinstance(post.media, list) else post.media
        hikaye_medya = str(hikaye_gorsel.hikaye_surumu(ham, post.is_video))
        story_id = instagram.hikaye_yayinla(hikaye_medya, post.is_video)
        state.mark_published(published_state, post.slug, "instagram_story", str(story_id))
        print(f"  ✅ hikaye paylaşıldı (id: {story_id})")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️  hikaye atılamadı: {exc}")


def _anma_gunu_mu() -> bool:
    """Bugun (TR saatiyle) content/bayramlar.json'da tur=anma olan bir gun mu."""
    import datetime as _dt
    import json as _json
    import pathlib as _pl
    from zoneinfo import ZoneInfo
    try:
        gunler = _json.loads(_pl.Path("content/bayramlar.json").read_text(encoding="utf-8"))["gunler"]
    except Exception:  # noqa: BLE001
        return False
    bugun = _dt.datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%m-%d")
    return any(g.get("tur") == "anma" and g.get("tarih") == bugun for g in gunler)


def run(only: str | None = None, force: bool = False, max_per_run: int | None = None) -> int:
    all_posts = posts.load_all()
    if not all_posts:
        print("posts/ klasöründe hiç post bulunamadı.")
        return 0

    if max_per_run is None:
        max_per_run = config.MAX_PER_RUN

    published_state = state.load()
    failures = 0
    did_anything = False
    yayinlanan = 0
    # Ayni calismada ayni platforma birden fazla gonderi gitmesin: birikmis
    # kuyruk bosalirken FB/Threads'e dakika arayla iki post dusuyordu.
    # Platformu dolu olan post o platformu sonraki tura birakir.
    turda_kullanilan: set[str] = set()

    for post in all_posts:
        if only and post.slug != only:
            continue
        if not force and not post.is_due():
            print(f"⏳ {post.slug} — zamanı gelmedi ({post.publish_at})")
            continue

        # Anma gunlerinde (10 Kasim, 15 Temmuz) bayram postu disinda paylasim yok;
        # urun/bilgi postu ertesi gunun turuna kalir (01.11.2026: 10.11'e iki post
        # planlanmisti, engelleyen kontrol yoktu).
        if not force and not only and "-bayram-" not in post.slug and _anma_gunu_mu():
            print(f"🕯️  {post.slug} — bugün anma günü, yarına kaldı")
            continue

        # Birikmiş postları tek seferde boşaltma: bot saat başı çalıştığı için
        # bekleyen kuyruk saatlere yayılarak paylaşılır, akış spam'e dönmez.
        if not only and max_per_run > 0 and yayinlanan >= max_per_run:
            print(f"⏸️  {post.slug} — bu çalışmanın sınırı doldu, sonraki tura kaldı")
            continue

        gonderildi = False
        for platform in post.platforms:
            # Bazi platformlar bu isin imajinda calisamaz (tiktok_studio
            # Playwright tarayicisi ister); onlari kendi isleri yayinlar.
            if platform in SKIP_PLATFORMS:
                continue
            publisher = PUBLISHERS.get(platform)
            if publisher is None:
                print(f"⚠️  {post.slug} — bilinmeyen platform: {platform}")
                continue
            if post.is_carousel and platform not in CAROUSEL_PLATFORMS:
                print(f"⚠️  {post.slug} — {platform} carousel desteklemiyor, atlandı")
                continue
            if not force and state.already_published(published_state, post.slug, platform):
                # 01.11.2026: feed postu gitmis ama hikayesi kalmissa yeniden dene.
                # Eskiden bu 'continue' hikaye adimini da atliyordu; 31.10 hikayeleri
                # hic tekrar denenmedi. Yalniz son 24 saatte paylasilan postlar icin.
                if platform == "instagram" and _hikaye_bekliyor(post, published_state):
                    _hikaye_dene(post, published_state)
                continue
            if not only and platform in turda_kullanilan:
                print(f"⏸️  {post.slug} → {platform} — bu turda bu platforma gönderildi, sonraki tura kaldı")
                continue

            print(f"→ {post.slug} → {platform}")
            did_anything = True
            try:
                result_id = _call(publisher, post)
                state.mark_published(published_state, post.slug, platform, str(result_id))
                print(f"  ✅ paylaşıldı (id: {result_id})")
                gonderildi = True
                turda_kullanilan.add(platform)
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  ❌ hata: {exc}")
                continue

            # Instagram'a giden her post ayrıca hikaye olarak da paylaşılır.
            # Hikaye hatası postu başarısız saymaz; ayrı anahtarla kaydedilir
            # ki sonraki turda yeniden denensin, feed postu tekrar atılmasın.
            if platform == "instagram":
                _hikaye_dene(post, published_state)

        # Post en az bir platforma gittiyse bu turun kotasından düşer.
        if gonderildi:
            yayinlanan += 1

    if not config.DRY_RUN:
        state.save(published_state)

    if not did_anything:
        print("Paylaşılacak yeni bir şey yok.")

    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Atölye Elektronik sosyal medya botu")
    parser.add_argument("--dry-run", action="store_true", help="Hiçbir şey paylaşma, sadece göster")
    parser.add_argument("--only", help="Sadece bu slug'a sahip postu işle")
    parser.add_argument("--force", action="store_true", help="Zaman ve tekrar kontrolünü atla")
    parser.add_argument(
        "--max", type=int, default=None, dest="max_per_run",
        help="Bu çalışmada en fazla kaç post paylaşılsın (0 = sınırsız)",
    )
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"
        config.DRY_RUN = True

    sys.exit(run(only=args.only, force=args.force, max_per_run=args.max_per_run))


if __name__ == "__main__":
    main()
