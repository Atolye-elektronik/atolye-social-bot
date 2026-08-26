"""TikTok Studio otomasyonunun komut satırı arayüzü."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

from .. import config, posts, state
from . import analytics, comments, upload
from .session import OturumDustu, StudioError, saglik_kontrol

PLATFORM = "tiktok_studio"


def zamanla(gun: int, maks: int) -> int:
    """Yaklaşan postları şimdiden TikTok'un zamanlayıcısına bırakır.

    Paylaşım anında CI'ın ayakta ve oturumun geçerli olmasına gerek kalmaz —
    video TikTok'ta beklediği için sonrasında oturum düşse bile çıkar. CI'da
    tarayıcı otomasyonuna güvenmenin en sağlam yolu bu.
    """
    tum = posts.load_all()
    if not tum:
        print("posts/ klasöründe hiç post yok.")
        return 0

    durum = state.load()
    simdi = dt.datetime.now(posts.TZ)
    # TikTok en fazla 10 gün sonrasına zamanlıyor.
    sinir = simdi + dt.timedelta(days=min(gun, 10))

    aday = []
    for post in tum:
        if PLATFORM not in post.platforms:
            continue
        if state.already_published(durum, post.slug, PLATFORM):
            continue
        if post.publish_at is None:
            print(f"⏭️  {post.slug} — publish_at yok, zamanlanamaz (main.py paylaşır)")
            continue
        if not (simdi + upload.EN_ERKEN <= post.publish_at <= sinir):
            continue
        if not post.is_video:
            print(f"⚠️  {post.slug} — TikTok için video gerekiyor, atlandı")
            continue
        aday.append(post)

    if not aday:
        print(f"Önümüzdeki {gun} gün içinde zamanlanacak yeni TikTok postu yok.")
        return 0

    print(f"{len(aday)} post bulundu, en fazla {maks} tanesi zamanlanacak.\n")

    hata = 0
    for post in aday[:maks]:
        print(f"→ {post.slug} → {post.publish_at:%Y-%m-%d %H:%M}")
        try:
            sonuc = upload.studio_paylas(post.tiktok_caption, post.media, post.publish_at)
            state.mark_published(durum, post.slug, PLATFORM, str(sonuc))
            print(f"  ✅ {sonuc}")
        except (OturumDustu, StudioError) as exc:
            hata += 1
            print(f"  ❌ {exc}")
            # Oturum düştüyse kalanları denemenin anlamı yok.
            if isinstance(exc, OturumDustu):
                break

    if not config.DRY_RUN:
        state.save(durum)
    return 1 if hata else 0


def tek_post(slug: str, hemen: bool) -> int:
    hedef = next((p for p in posts.load_all() if p.slug == slug), None)
    if hedef is None:
        print(f"Post bulunamadı: {slug}")
        return 1
    if not hedef.is_video:
        print(f"{slug} bir video değil — TikTok video istiyor.")
        return 1

    ne_zaman = None if hemen else hedef.publish_at
    try:
        sonuc = upload.studio_paylas(hedef.tiktok_caption, hedef.media, ne_zaman)
    except (OturumDustu, StudioError) as exc:
        print(f"❌ {exc}")
        return 1

    durum = state.load()
    state.mark_published(durum, hedef.slug, PLATFORM, str(sonuc))
    if not config.DRY_RUN:
        state.save(durum)
    print(f"✅ {sonuc}")
    return 0


def main(argv: list[str] | None = None) -> int:
    # --dry-run hem komuttan önce hem sonra yazılabilsin diye ortak bir üst
    # ayrıştırıcıda duruyor. SUPPRESS olmazsa alt komutun varsayılanı üsttekini
    # ezer ve "--dry-run zamanla" sessizce gerçek paylaşım yapardı.
    ortak = argparse.ArgumentParser(add_help=False)
    ortak.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Hiçbir şey yayınlama, sadece ne olacağını göster",
    )

    parser = argparse.ArgumentParser(
        prog="python -m src.tiktok_studio",
        description="TikTok Studio otomasyonu",
        parents=[ortak],
    )
    alt = parser.add_subparsers(dest="komut", required=True)

    p_zamanla = alt.add_parser(
        "zamanla", parents=[ortak], help="Yaklaşan postları TikTok'a planla"
    )
    p_zamanla.add_argument("--gun", type=int, default=7, help="Kaç gün ilerisi (en fazla 10)")
    p_zamanla.add_argument("--maks", type=int, default=3, help="Bu çalışmada en fazla kaç video")

    p_yukle = alt.add_parser("yukle", parents=[ortak], help="Tek bir postu yükle")
    p_yukle.add_argument("post", help="Post dosya adı (.md olmadan)")
    p_yukle.add_argument("--hemen", action="store_true", help="Zamanlama yerine hemen yayınla")

    alt.add_parser("analitik", parents=[ortak], help="Analitiği çek ve state/ altına yaz")
    alt.add_parser("yorumlar", parents=[ortak], help="Yorumları topla, yanıt taslağı üret")
    alt.add_parser("saglik", parents=[ortak], help="Oturum geçerli mi, çerez ne zaman düşecek")

    args = parser.parse_args(argv)

    if getattr(args, "dry_run", False):
        os.environ["DRY_RUN"] = "true"
        config.DRY_RUN = True

    try:
        if args.komut == "zamanla":
            return zamanla(args.gun, args.maks)
        if args.komut == "yukle":
            return tek_post(args.post, args.hemen)
        if args.komut == "analitik":
            return analytics.calistir()
        if args.komut == "yorumlar":
            return comments.calistir()
        if args.komut == "saglik":
            return saglik_kontrol()
    except OturumDustu as exc:
        print(f"❌ {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
