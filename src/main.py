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

from . import config, facebook, instagram, posts, state, tiktok, youtube

PUBLISHERS = {
    "instagram": instagram.publish,
    "facebook": facebook.publish,
    "tiktok": tiktok.publish,
    "youtube": youtube.publish,
}


CAROUSEL_PLATFORMS = {"instagram", "facebook"}


def _call(publisher, post):
    """Yayıncıyı çağırır; 'extra' parametresi destekliyorsa onu da geçirir."""
    params = inspect.signature(publisher).parameters
    if "extra" in params:
        return publisher(post.caption, post.media, post.is_video, extra=post.extra)
    return publisher(post.caption, post.media, post.is_video)


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

    for post in all_posts:
        if only and post.slug != only:
            continue
        if not force and not post.is_due():
            print(f"⏳ {post.slug} — zamanı gelmedi ({post.publish_at})")
            continue

        # Birikmiş postları tek seferde boşaltma: bot saat başı çalıştığı için
        # bekleyen kuyruk saatlere yayılarak paylaşılır, akış spam'e dönmez.
        if not only and max_per_run > 0 and yayinlanan >= max_per_run:
            print(f"⏸️  {post.slug} — bu çalışmanın sınırı doldu, sonraki tura kaldı")
            continue

        gonderildi = False
        for platform in post.platforms:
            publisher = PUBLISHERS.get(platform)
            if publisher is None:
                print(f"⚠️  {post.slug} — bilinmeyen platform: {platform}")
                continue
            if post.is_carousel and platform not in CAROUSEL_PLATFORMS:
                print(f"⚠️  {post.slug} — {platform} carousel desteklemiyor, atlandı")
                continue
            if not force and state.already_published(published_state, post.slug, platform):
                continue

            print(f"→ {post.slug} → {platform}")
            did_anything = True
            try:
                result_id = _call(publisher, post)
                state.mark_published(published_state, post.slug, platform, str(result_id))
                print(f"  ✅ paylaşıldı (id: {result_id})")
                gonderildi = True
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  ❌ hata: {exc}")

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
