# -*- coding: utf-8 -*-
"""Blog yazıları için kapak görseli üretir.

28.08: `atolyeelektronik.com/blogs/haberler` listesinde bir yazının kapağı
yoktu — Shopify o yazıyı boş kutuyla gösteriyor ve listede göze batıyor.
Ayrıca kapaksız yazı sosyal medyada ve aramada önizleme görseli üretemiyor.

Ürün fotoğrafı koymak yerine yazının **kendi yapısını** gösteriyoruz: kontrol
listesi yazısına kontrol listesi kapağı. Okuyucu daha tıklamadan içeride ne
olduğunu görüyor.

    python tools/blog_kapak.py
"""

from __future__ import annotations

import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw  # noqa: E402

from src.carousel_gorsel import (  # noqa: E402
    ALTIN, BEYAZ, TURUNCU,
    _aralikli, _aralikli_genislik, _bold, _devre_izi, _mono, _normal, _sigdir,
)

KOK = pathlib.Path(__file__).resolve().parents[1]
CIKTI = KOK / "posts" / "media" / "blog-kapak"
LOGO = KOK / "posts" / "media" / "marka" / "logo.png"

W, H = 1600, 900                      # Shopify blog kapağı için geniş oran

ZEMIN = (245, 248, 250)
LACIVERT = (11, 20, 32)
TEAL = (13, 132, 124)
GRI = (104, 120, 136)

KAPAKLAR = [
    {
        "dosya": "donem-basi-kontrol-listesi.png",
        "ustserit": "MESLEKİ VE TEKNİK ANADOLU LİSELERİ İÇİN",
        "baslik": "Dönem Başı Kontrol Listesi",
        "maddeler": [
            "Temrin defteri",
            "Staj (işletmelerde mesleki eğitim) dosyası",
            "Takım çantası",
            "Ders setleri — endüstriyel elektronik, Arduino",
            "Fen deney setleri",
        ],
        "alt": "atolyeelektronik.com · Atölye Günlüğü",
    },
]


def _zemin() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    tuval = Image.new("RGB", (W, H), ZEMIN)
    katman = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    kd = ImageDraw.Draw(katman)
    rnd = random.Random("blog-kapak")
    _devre_izi(kd, rnd, (0, 0, W, 150), adet=6)
    _devre_izi(kd, rnd, (0, H - 150, W, H), adet=6)
    katman.putalpha(katman.getchannel("A").point(lambda a: int(a * 0.26)))
    tuval = Image.alpha_composite(tuval.convert("RGBA"), katman)

    # Logo zemine yedirilmiş filigran — reklam görselleriyle aynı dil
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((300, 300), Image.LANCZOS)
    logo.putalpha(logo.getchannel("A").point(lambda a: int(a * 0.12)))
    tuval.alpha_composite(logo, (W - logo.width - 40, H - logo.height - 40))

    tuval = tuval.convert("RGB")
    return tuval, ImageDraw.Draw(tuval)


def _tik(d: ImageDraw.ImageDraw, x: int, y: int, boy: int = 34) -> None:
    """Yuvarlak köşeli kutu + tik işareti."""
    d.rounded_rectangle([x, y, x + boy, y + boy], radius=8, outline=TEAL, width=3)
    d.line([(x + 8, y + boy * 0.55), (x + boy * 0.42, y + boy - 9),
            (x + boy - 7, y + 9)], fill=TEAL, width=4, joint="curve")


def uret(kapak: dict) -> pathlib.Path:
    tuval, d = _zemin()

    # Üst şerit — kime seslendiğimiz
    fs = _mono(24)
    gen = _aralikli_genislik(d, kapak["ustserit"], fs, aralik=6)
    _aralikli(d, ((W - gen) / 2, 74), kapak["ustserit"], fs, TURUNCU, aralik=6)
    d.line([(W / 2 - 60, 50), (W / 2 + 60, 50)], fill=ALTIN, width=4)

    # Başlık
    fb, satirlar, boyut = _sigdir(d, kapak["baslik"], W - 240, [([88, 78], 2), ([64], 3)])
    y = 150
    for s in satirlar:
        d.text(((W - d.textlength(s, font=fb)) / 2, y), s, font=fb, fill=LACIVERT)
        y += int(boyut * 1.18)

    # Kontrol listesi — yazının yapısı kapakta görünüyor
    y += 40
    fm = _normal(38)
    en_genis = max(d.textlength(m, font=fm) for m in kapak["maddeler"])
    x0 = int((W - (en_genis + 62)) / 2)
    for madde in kapak["maddeler"]:
        _tik(d, x0, y)
        d.text((x0 + 62, y - 2), madde, font=fm, fill=(44, 60, 78))
        y += 62

    # Alt satır
    fa = _normal(26)
    d.text(((W - d.textlength(kapak["alt"], font=fa)) / 2, H - 74),
           kapak["alt"], font=fa, fill=GRI)

    CIKTI.mkdir(parents=True, exist_ok=True)
    yol = CIKTI / kapak["dosya"]
    tuval.save(yol)
    return yol


def main() -> int:
    for k in KAPAKLAR:
        yol = uret(k)
        print(f"  uretildi: {yol.name}  ({yol.stat().st_size // 1024} KB)")
    print(f"\n{len(KAPAKLAR)} kapak -> {CIKTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
