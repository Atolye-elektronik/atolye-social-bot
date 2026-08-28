# -*- coding: utf-8 -*-
"""Defter kapağı üretir — MTAL ve MESEM varyantları, MEB amblemi olmadan.

Neden gerekti: staj defterinin kapağında "MESLEKİ VE TEKNİK ANADOLU LİSESİ"
yazıyor, ama ürünü MESEM'e de satıyoruz (Shopify'daki adı bile "Meslek Lisesi
ve MESEM Öğrencileri için"). MESEM reklamında MTAL yazan bir kapak göstermek
alıcıya "bu benim için değil" dedirtiyor.

İki kural:
  * **MEB amblemi yok.** Trendyol defterleri amblem yüzünden reddetmişti;
    reklamda da resmî onay izlenimi vermek istemiyoruz.
  * **Kurum satırı hitap, ad değil.** "…LİSELERİ İÇİN" / "…MERKEZLERİ İÇİN" —
    tekil yazılınca kapak okulun kendi adıymış gibi okunuyor.

Çıktı A4 / 300 dpi, baskıya verilebilir.

    python tools/defter_kapak.py
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

KOK = pathlib.Path(__file__).resolve().parents[1]
CIKTI = KOK / "posts" / "media" / "defter-kapak"

# A4, 300 dpi
W, H = 2480, 3508

USTSOL = (23, 126, 160)      # teal
ALTSAG = (108, 199, 74)      # yeşil
LACIVERT = (20, 58, 92)
ORTA = (26, 104, 122)
BEYAZ = (255, 255, 255)

SERIF = ("georgia.ttf", "times.ttf", "DejaVuSerif.ttf")
SERIF_BOLD = ("georgiab.ttf", "timesbd.ttf", "DejaVuSerif-Bold.ttf")
SANS_BOLD = ("arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf")
SANS = ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf")

KAPAKLAR = [
    {
        "dosya": "kapak-staj-mtal.png",
        "kurum": "MESLEKİ VE TEKNİK ANADOLU LİSELERİ İÇİN",
        "baslik": ["İŞLETMELERDE", "MESLEK EĞİTİMİ", "ÖĞRENCİ İŞ DOSYASI"],
        "alanlar": ["ADI SOYADI", "SINIFI / NO", "ALANI", "DALI", "İŞLETME ADI"],
    },
    {
        "dosya": "kapak-staj-mesem.png",
        "kurum": "MESLEKİ EĞİTİM MERKEZLERİ İÇİN",
        "baslik": ["İŞLETMELERDE", "MESLEK EĞİTİMİ", "ÖĞRENCİ İŞ DOSYASI"],
        # MESEM'de öğrenci bir işletmeye sözleşmeyle bağlı; usta öğretici
        # alanı MTAL kapağında yok, burada olmalı.
        "alanlar": ["ADI SOYADI", "SINIFI / NO", "ALANI", "İŞLETME ADI",
                    "USTA ÖĞRETİCİ"],
    },
]


def _font(adaylar: tuple[str, ...], boyut: int) -> ImageFont.FreeTypeFont:
    for ad in adaylar:
        for kok in (r"C:\Windows\Fonts", "/usr/share/fonts/truetype/dejavu"):
            yol = pathlib.Path(kok) / ad
            if yol.exists():
                return ImageFont.truetype(str(yol), boyut)
    raise SystemExit(f"HATA: yazi tipi bulunamadi -> {adaylar}")


def _gradyan() -> Image.Image:
    """Sol üstten sağ alta çapraz geçiş.

    Küçük bir tuvale çizilip büyütülüyor; 2480x3508 üzerinde piksel piksel
    dolaşmak gereksiz yavaş ve sonuç aynı.
    """
    kucuk = Image.new("RGB", (124, 176))
    p = kucuk.load()
    for y in range(kucuk.height):
        for x in range(kucuk.width):
            t = (x / kucuk.width + y / kucuk.height) / 2
            p[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(USTSOL, ALTSAG))
    return kucuk.resize((W, H), Image.BICUBIC)


def _ucgenler(d: ImageDraw.ImageDraw) -> None:
    """Sol üst ve sağ alt köşedeki düşük poligon deseni."""
    b = 300  # birim üçgen kenarı
    desen = [
        # (sütun, satır, yön, renk)  — sol üst küme
        (0, 0, "sag", LACIVERT), (1, 0, "sol", ORTA), (1, 0, "sag", LACIVERT),
        (2, 0, "sol", ORTA), (0, 1, "sag", ORTA), (1, 1, "sol", LACIVERT),
    ]
    for sut, sat, yon, renk in desen:
        x, y = sut * b, sat * b
        if yon == "sag":
            ucgen = [(x, y), (x + b, y), (x, y + b)]
        else:
            ucgen = [(x + b, y), (x + b, y + b), (x, y + b)]
        d.polygon(ucgen, fill=renk)

    for sut, sat, yon, renk in desen:
        x, y = W - sut * b, H - sat * b
        if yon == "sag":
            ucgen = [(x, y), (x - b, y), (x, y - b)]
        else:
            ucgen = [(x - b, y), (x - b, y - b), (x, y - b)]
        d.polygon(ucgen, fill=renk)


def _aralikli(d, xy, metin, font, renk, aralik):
    x, y = xy
    for harf in metin:
        d.text((x, y), harf, font=font, fill=renk)
        x += d.textlength(harf, font=font) + aralik


def _aralikli_gen(d, metin, font, aralik) -> float:
    return sum(d.textlength(h, font=font) for h in metin) + aralik * (len(metin) - 1)


def uret(kapak: dict) -> pathlib.Path:
    tuval = _gradyan()
    d = ImageDraw.Draw(tuval)
    _ucgenler(d)

    # Noktalı ayraç — amblemin bıraktığı boşluğu bu doldurmuyor, kompozisyon
    # bilerek yukarıdan başlıyor.
    y = 1090
    nokta_f = _font(SANS_BOLD, 44)
    nokta = "." * 60
    d.text(((W - d.textlength(nokta, font=nokta_f)) / 2, y), nokta,
           font=nokta_f, fill=BEYAZ)

    # Kurum satırı — hitap, ad değil
    y += 150
    kf = _font(SERIF_BOLD, 74)
    while _aralikli_gen(d, kapak["kurum"], kf, 6) > W - 320 and kf.size > 40:
        kf = _font(SERIF_BOLD, kf.size - 2)
    _aralikli(d, ((W - _aralikli_gen(d, kapak["kurum"], kf, 6)) / 2, y),
              kapak["kurum"], kf, BEYAZ, 6)

    # Başlık
    y += 220
    bf = _font(SANS_BOLD, 150)
    for satir in kapak["baslik"]:
        f = bf
        while d.textlength(satir, font=f) > W - 280 and f.size > 80:
            f = _font(SANS_BOLD, f.size - 4)
        d.text(((W - d.textlength(satir, font=f)) / 2, y), satir, font=f, fill=BEYAZ)
        y += int(bf.size * 1.18)

    # Öğrenci kutusu
    y += 150
    kx0, kx1 = 380, W - 380
    ky1 = y + 130 + len(kapak["alanlar"]) * 130
    d.rounded_rectangle([kx0, y, kx1, ky1], radius=40, outline=BEYAZ, width=6)

    ef = _font(SERIF, 70)
    d.text((kx0 + 60, y + 40), "ÖĞRENCİNİN;", font=ef, fill=BEYAZ)

    af = _font(SERIF_BOLD, 52)
    cf = _font(SANS, 52)
    sy = y + 160
    etiket_gen = max(d.textlength(a, font=af) for a in kapak["alanlar"])
    for alan in kapak["alanlar"]:
        d.text((kx0 + 60, sy), alan, font=af, fill=BEYAZ)
        x = kx0 + 60 + etiket_gen + 50
        d.text((x, sy), ":", font=cf, fill=BEYAZ)
        d.text((x + 40, sy), "." * 46, font=cf, fill=BEYAZ)
        sy += 130

    CIKTI.mkdir(parents=True, exist_ok=True)
    yol = CIKTI / kapak["dosya"]
    tuval.save(yol, dpi=(300, 300))
    return yol


def main() -> int:
    for k in KAPAKLAR:
        yol = uret(k)
        print(f"  uretildi: {yol.name}  ({yol.stat().st_size // 1024} KB)")
    print(f"\n{len(KAPAKLAR)} kapak -> {CIKTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
