"""Okul fiyat listesi karuselini Instagram'da yayımlar.

Görseller repoda değil, Shopify CDN'inde duruyor — `pazarlama/karusel/*.html`
dosyalarından Playwright ile üretilip oraya yüklendiler. Kalıcı ve herkese açık
adresler olduğu için `MEDIA_BASE_URL` ayarlanmasına gerek yok; `config.media_url`
mutlak adresleri olduğu gibi geçiriyor.

Bu iş CI'da çalışacak şekilde tasarlandı: `META_ACCESS_TOKEN` GitLab CI
değişkenlerinde duruyor, yerelde bir kopyasının bulunmasına gerek yok.

    Kuru çalıştırma:  DRY_RUN=true python -m src.ig_fiyat_karuseli
    Gerçek yayın:     python -m src.ig_fiyat_karuseli
"""

from __future__ import annotations

import pathlib
import sys

from . import config, instagram

ALTYAZI_DOSYA = pathlib.Path("pazarlama/ig-altyazi.txt")

_TABAN = "https://cdn.shopify.com/s/files/1/0801/9692/7717/files/ig-karusel-{}.png?v={}"

# Slayt 3 CDN'e bir saniye sonra düştüğü için sürüm damgası diğerlerinden farklı.
# Yanlış damga 404 veriyor, o yüzden tek tek yazılı.
GORSELLER = [
    _TABAN.format(1, "1786875177"),
    _TABAN.format(2, "1786875177"),
    _TABAN.format(3, "1786875178"),
    _TABAN.format(4, "1786875177"),
    _TABAN.format(5, "1786875177"),
]


def main() -> int:
    if not config.META_TOKEN and not config.DRY_RUN:
        print(
            "META_ACCESS_TOKEN tanimli degil. Bu is GitLab CI'da calistirilmali "
            "(CI/CD > Pipelines > Run pipeline > JOB=ig-karusel).",
            file=sys.stderr,
        )
        return 1

    if not ALTYAZI_DOSYA.exists():
        print(f"Altyazi dosyasi yok: {ALTYAZI_DOSYA}", file=sys.stderr)
        return 1

    altyazi = ALTYAZI_DOSYA.read_text(encoding="utf-8").strip()
    print(f"{len(GORSELLER)} slayt, altyazi {len(altyazi)} karakter.")

    gonderi_id = instagram.publish_carousel(altyazi, GORSELLER)
    print(f"Yayinlandi: {gonderi_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
