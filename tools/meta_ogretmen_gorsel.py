# -*- coding: utf-8 -*-
"""Meta reklamları için öğretmene yönelik görseller üretir.

Neden ayrı bir araç: elimizdeki 53 video ve carousel slaytı ÖĞRENCİYE
sesleniyor — ürünü anlatıyor. Öğretmen mesajı bambaşka: ürünü değil **çözümü**
anlatır ("tüm sınıf, tek sipariş, tek fatura").

İki tasarım kararı, ikisi de kullanıcı uyarısıyla düzeltildi:
  * **Açık zemin.** Facebook akışı beyaz; koyu görsel orada ağır duruyor ve
    öğretmen kitlesine kurumsal görünmek istiyoruz. Marka renkleri aynı,
    yalnız roller yer değiştirdi — lacivert artık zemin değil METİN.
  * **Ürün fotoğrafı ana öğe.** Akışta durduran şey fotoğraftır; salt metin
    kart kaydırılıp geçilir. Metin kısa tutuldu, işi fotoğraf yapıyor.

Kitleyi görselin kendisi eliyor: üstteki turuncu şerit doğrudan "MESLEK
LİSESİ ÖĞRETMENLERİNE" diyor. Meta'da meslek hedeflemesi kalmadığı için
(bkz. meta-ads-kurulum.md) eleme işini yaratıcı yapıyor.

    python tools/meta_ogretmen_gorsel.py
"""

from __future__ import annotations

import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw  # noqa: E402

from src.carousel_gorsel import (  # noqa: E402
    ALTIN, BEYAZ, TURUNCU, H, W,
    _aralikli, _aralikli_genislik, _bold, _devre_izi, _indir, _kaydet,
    _mono, _normal, _sigdir,
)

SERIT = "MESLEK LİSESİ ÖĞRETMENLERİNE"
MARKA = "ATÖLYE ELEKTRONİK"
SITE = "atolyeelektronik.com"

ZEMIN = (245, 248, 250)      # saf beyaz değil — akışta kaybolmasın
LACIVERT = (11, 20, 32)      # başlık
TEAL = (13, 132, 124)        # turkuazın açık zeminde okunan tonu
GRI = (104, 120, 136)

CDN = "https://cdn.shopify.com/s/files/1/0801/9692/7717/files/"

REKLAMLAR = [
    {
        "dosya": "meta-ogretmen-defter.png",
        "foto": CDN + "isdosyasi1_377200c3-0c47-452a-9bde-8c9dcd1ac333.webp?v=1784792291",
        "baslik": "Sınıfın tamamı, tek sipariş",
        "destek": "10, 20 ve 30'lu sınıf paketleri · tek fatura · aynı gün kargo",
        "rozet": "STAJ VE TEMRİN DEFTERİ",
    },
    {
        "dosya": "meta-ogretmen-takim-cantasi.png",
        "foto": CDN + "Takimcantasi.png?v=1785258195",
        "baslik": "Atölye dersine hazır sınıf",
        "destek": "17 parça tam set · sınıf adedi kadar tek seferde",
        "rozet": "MESLEK LİSESİ TAKIM ÇANTASI",
    },
    {
        "dosya": "meta-ogretmen-endustriyel.png",
        "foto": CDN + "EndElkhepsi.webp?v=1782335968",
        "baslik": "11. sınıf müfredatına birebir",
        "destek": "Her öğrenci aynı setle çalışır, ders tek elden yürür",
        "rozet": "ENDÜSTRİYEL ELEKTRONİK SETİ",
    },
    {
        "dosya": "meta-ogretmen-arduino.png",
        "foto": CDN + "Baslangicseti.png?v=1785260927",
        "baslik": "Proje dersine hazır set",
        "destek": "Kutulu setler · Türkçe kaynak ve devre örnekleri",
        "rozet": "ARDUINO EĞİTİM SETLERİ",
    },
]

CIKTI_DIZIN = pathlib.Path(__file__).resolve().parents[1] / "posts" / "media" / "meta-ogretmen"

# Fotograf kartinin yerlesimi
KART = (70, 250, W - 70, 830)


def _zemin_ac(seed: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Açık zemin + soluk devre izleri.

    İzler ayrı katmana çizilip düşük opaklıkla bindiriliyor; doğrudan
    çizilince açık zeminde baskın çıkıp metnin önüne geçiyorlar.
    """
    tuval = Image.new("RGB", (W, H), ZEMIN)
    katman = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    kd = ImageDraw.Draw(katman)
    rnd = random.Random(seed)
    _devre_izi(kd, rnd, (0, 0, W, 200), adet=7)
    _devre_izi(kd, rnd, (0, H - 200, W, H), adet=7)
    katman.putalpha(katman.getchannel("A").point(lambda a: int(a * 0.28)))
    tuval = Image.alpha_composite(tuval.convert("RGBA"), katman).convert("RGB")
    return tuval, ImageDraw.Draw(tuval)


def _foto_kart(tuval: Image.Image, d: ImageDraw.ImageDraw, url: str) -> None:
    """Ürün fotoğrafını beyaz yuvarlak kartın içine oranını bozmadan yerleştirir."""
    x0, y0, x1, y1 = KART
    d.rounded_rectangle([x0, y0, x1, y1], radius=28, fill=BEYAZ,
                        outline=(226, 233, 239), width=2)

    foto = _indir(url).convert("RGB")
    ic_w, ic_h = (x1 - x0) - 56, (y1 - y0) - 56
    olcek = min(ic_w / foto.width, ic_h / foto.height)
    yeni = foto.resize((max(1, int(foto.width * olcek)), max(1, int(foto.height * olcek))),
                       Image.LANCZOS)
    px = x0 + ((x1 - x0) - yeni.width) // 2
    py = y0 + ((y1 - y0) - yeni.height) // 2
    tuval.paste(yeni, (px, py))


def uret(reklam: dict) -> pathlib.Path:
    tuval, d = _zemin_ac(f"ogretmen:{reklam['dosya']}")

    # Marka
    f = _mono(28)
    gen = _aralikli_genislik(d, MARKA, f, aralik=8)
    _aralikli(d, ((W - gen) / 2, 92), MARKA, f, TEAL, aralik=8)
    d.line([(W / 2 - 60, 66), (W / 2 + 60, 66)], fill=ALTIN, width=4)

    # Kitleyi eleyen şerit
    fs = _mono(30)
    gen = _aralikli_genislik(d, SERIT, fs, aralik=8)
    _aralikli(d, ((W - gen) / 2, 168), SERIT, fs, TURUNCU, aralik=8)

    _foto_kart(tuval, d, reklam["foto"])
    d = ImageDraw.Draw(tuval)

    # Asıl vaat
    fb, satirlar, boyut = _sigdir(
        d, reklam["baslik"], W - 160, [([72, 64], 2), ([56], 3)]
    )
    y = 880
    for s in satirlar:
        d.text(((W - d.textlength(s, font=fb)) / 2, y), s, font=fb, fill=LACIVERT)
        y += int(boyut * 1.2)

    d.line([(W / 2 - 110, y + 26), (W / 2 + 110, y + 26)], fill=TEAL, width=4)

    # Destek cümlesi — gerekirse küçülterek tek satırda tut
    fd = _normal(34)
    while d.textlength(reklam["destek"], font=fd) > W - 140 and fd.size > 24:
        fd = _normal(fd.size - 2)
    d.text(((W - d.textlength(reklam["destek"], font=fd)) / 2, y + 76),
           reklam["destek"], font=fd, fill=GRI)

    # Rozet
    fr = _mono(24)
    gen = _aralikli_genislik(d, reklam["rozet"], fr, aralik=6)
    _aralikli(d, ((W - gen) / 2, y + 146), reklam["rozet"], fr, TEAL, aralik=6)

    # CTA
    fp = _bold(38)
    gen = d.textlength(SITE, font=fp)
    ph, pw = 84, gen + 120
    x0, y0 = (W - pw) / 2, 1230 - ph / 2
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph / 2, fill=TURUNCU)
    d.text(((W - gen) / 2, 1230 - 26), SITE, font=fp, fill=BEYAZ)

    CIKTI_DIZIN.mkdir(parents=True, exist_ok=True)
    return _kaydet(tuval, CIKTI_DIZIN / reklam["dosya"])


def main() -> int:
    for r in REKLAMLAR:
        yol = uret(r)
        print(f"  uretildi: {yol.name}  ({yol.stat().st_size // 1024} KB)")
    print(f"\n{len(REKLAMLAR)} gorsel -> {CIKTI_DIZIN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
