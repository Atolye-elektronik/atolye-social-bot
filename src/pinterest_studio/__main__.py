"""Pinterest arayüz otomasyonunun komut satırı arayüzü.

    python -m src.pinterest_studio saglik              # oturum ayakta mı
    python -m src.pinterest_studio panolar             # hesaptaki panoları listele
    python -m src.pinterest_studio dene --only SLUG    # tek postu arayüzden at
"""

from __future__ import annotations

import argparse
import sys

from .. import config, posts
from . import selectors, upload
from .session import OturumDustu, StudioError, gorunmesini_bekle, saglik_kontrol
from .session import pinterest as pinterest_oturumu

PLATFORM = "pinterest_studio"


def panolar() -> int:
    """Hesaptaki panoları listeler — `pinterest_board` satırına yazacağın adlar.

    Panoları profil sayfasından okuyoruz; pin oluşturma ekranındaki seçici
    görsel yüklenmeden açılmıyor, sırf liste için taslak bırakmak istemiyoruz.
    """
    with pinterest_oturumu("https://www.pinterest.com/") as page:
        profil = gorunmesini_bekle(page, selectors.PROFIL_BAGLANTISI, "profil bağlantısı")
        adres = profil.get_attribute("href") or ""
        if not adres:
            print("Profil bağlantısı okunamadı.")
            return 1

        page.goto(
            f"https://www.pinterest.com{adres}{selectors.PANO_SEKMESI}",
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(5000)

        adlar = []
        for eleman in page.locator(selectors.PANO_KARTI[0]).all():
            tid = eleman.get_attribute("data-test-id") or ""
            ad = tid[len(selectors.PANO_KARTI_ONEKI):].strip()
            if ad:
                adlar.append(ad)

        adlar = list(dict.fromkeys(adlar))
        if not adlar:
            print("Pano bulunamadı — Pinterest'te henüz pano açmamış olabilirsin.")
            return 1

        print("Panoların:\n")
        for ad in adlar:
            print(f"  {ad}")
        print("\nBirini PINTEREST_BOARD değişkenine ya da post dosyasındaki")
        print("'pinterest_board:' satırına yaz.")
    return 0


def dene(slug: str) -> int:
    """Tek bir postu arayüzden Pinterest'e atar (durum kaydına dokunmaz)."""
    hedef = next((p for p in posts.load_all() if p.slug == slug), None)
    if hedef is None:
        print(f"'{slug}' adında bir post bulunamadı.")
        return 1

    print(f"→ {hedef.slug} → pinterest (arayüz)")
    try:
        pin_id = upload.studio_paylas(
            hedef.caption, hedef.media, hedef.is_video, extra=hedef.extra
        )
    except (OturumDustu, StudioError) as exc:
        print(f"  ❌ {exc}")
        return 1
    print(f"  ✅ paylaşıldı (pin: {pin_id})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pinterest arayüz otomasyonu")
    alt = parser.add_subparsers(dest="komut", required=True)

    alt.add_parser("saglik", help="Oturum ayakta mı, çerez ne zaman düşecek")
    alt.add_parser("panolar", help="Hesaptaki panoları listele")

    p_dene = alt.add_parser("dene", help="Tek bir postu arayüzden paylaş")
    p_dene.add_argument("--only", required=True, help="Post dosya adı (.md olmadan)")
    p_dene.add_argument("--dry-run", action="store_true", help="Paylaşma, ne olacağını göster")

    args = parser.parse_args(argv)

    if getattr(args, "dry_run", False):
        config.DRY_RUN = True

    if args.komut == "saglik":
        return saglik_kontrol()
    if args.komut == "panolar":
        return panolar()
    return dene(args.only)


if __name__ == "__main__":
    sys.exit(main())
