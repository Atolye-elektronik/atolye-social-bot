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

# Görseller depoda; proje public olduğu için raw adresleri dışarıdan açılıyor.
# Shopify CDN'e ayrıca yüklemeye gerek yok: Instagram görseli yayın anında bir
# kez indirip kendi kopyasını saklıyor, adresin kalıcı olması gerekmiyor.
_TABAN = (
    "https://gitlab.com/atolye-elektronik-group/atolye-social-bot"
    "/-/raw/main/pazarlama/karusel/karusel-{}.png"
)

GORSELLER = [_TABAN.format(i) for i in range(1, 6)]


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
