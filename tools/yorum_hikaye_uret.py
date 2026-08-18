# -*- coding: utf-8 -*-
"""Trendyol/Hepsiburada yorumlarindan 1080x1920 hikaye gorselleri uretir.

Kullanim: python tools/yorum_hikaye_uret.py
Cikti: posts/media/hikaye/hikaye-yorum-*.png
"""
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, REPO)

from PIL import Image, ImageDraw
from src.carousel_gorsel import (
    ZEMIN, ZEMIN_ACIK, TURKUAZ, TURUNCU, BEYAZ, GRI, ALTIN,
    SITE, MARKA, _bold, _normal, _sar, _devre_izi, _aralikli, _aralikli_genislik,
)

W, H = 1080, 1920
CIKTI = os.path.join(REPO, "posts", "media", "hikaye")

YORUMLAR = [
    {
        "slug": "yorum-arduino-seti",
        "platform": "Trendyol",
        "urun": "Arduino Başlangıç Seti 46 Parça",
        "yildiz": 5,
        "metin": "Ürün gerçekten çok iyi çalışıyor, fiyatı da çok uygun. Ellerinize sağlık, teşekkür ediyorum.",
        "kaynak": "Trendyol müşterisi · Nisan 2026",
    },
    {
        "slug": "yorum-pense",
        "platform": "Trendyol",
        "urun": "Pense 180 mm",
        "yildiz": 5,
        "metin": "Güzel ve kaliteli, hediye edildi.",
        "kaynak": "Trendyol müşterisi · Nisan 2026",
    },
    {
        "slug": "yorum-lcd",
        "platform": "Hepsiburada",
        "urun": "16x2 LCD Ekran I2C Modüllü",
        "yildiz": 5,
        "metin": "Çok güzel, özenle paketlenmiş. Hediye için teşekkürler.",
        "kaynak": "Hepsiburada müşterisi · Haziran 2026",
    },
    {
        "slug": "yorum-pil-yuvasi",
        "platform": "Hepsiburada",
        "urun": "2'li 18650 Pil Yuvası Kablolu",
        "yildiz": 5,
        "metin": "Ürün görselde olduğu gibi geldi. Hediyeler için teşekkürler.",
        "kaynak": "Hepsiburada müşterisi · Ağustos 2026",
    },
]


def _zemin(slug: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), ZEMIN)
    d = ImageDraw.Draw(img, "RGBA")
    # ust ve alt seritlerde soluk devre izleri
    rnd = random.Random(sum(map(ord, slug)))
    _devre_izi(d, rnd, (60, 40, W - 60, 165), adet=6)
    _devre_izi(d, rnd, (60, H - 380, W - 60, H - 120), adet=7)
    return img, d


def _ust_baslik(d: ImageDraw.ImageDraw) -> None:
    f = _bold(38)
    metin = "MÜŞTERİLERİMİZ NE DİYOR?"
    gw = _aralikli_genislik(d, metin, f, aralik=6)
    _aralikli(d, ((W - gw) / 2, 210), metin, f, TURKUAZ, aralik=6)


def _yildizlar(d: ImageDraw.ImageDraw, cx: int, y: int, adet: int = 5, boy: int = 52) -> None:
    """Basit besgen yildizlar, altin renkte."""
    import math
    toplam = adet * boy + (adet - 1) * 28
    x = cx - toplam // 2 + boy // 2
    for _ in range(adet):
        pts = []
        for i in range(10):
            aci = -math.pi / 2 + i * math.pi / 5
            r = boy / 2 if i % 2 == 0 else boy / 4.6
            pts.append((x + r * math.cos(aci), y + r * math.sin(aci)))
        d.polygon(pts, fill=ALTIN)
        x += boy + 28
def _rozet(d: ImageDraw.ImageDraw, cy: int, platform: str) -> None:
    f = _bold(34)
    metin = platform.replace("i", "İ").upper()  # Turkce buyuk I
    tw = d.textlength(metin, font=f)
    pad = 34
    x0 = (W - tw) / 2 - pad
    x1 = (W + tw) / 2 + pad
    d.rounded_rectangle([x0, cy - 38, x1, cy + 38], radius=38,
                        outline=TURUNCU, width=3)
    d.text(((W - tw) / 2, cy - 24), metin, font=f, fill=TURUNCU)


def _alt_bilgi(d: ImageDraw.ImageDraw) -> None:
    f1 = _bold(40)
    tw = d.textlength(MARKA, font=f1)
    d.text(((W - tw) / 2, H - 250), MARKA, font=f1, fill=BEYAZ)
    f2 = _normal(34)
    tw = d.textlength(SITE, font=f2)
    d.text(((W - tw) / 2, H - 190), SITE, font=f2, fill=TURKUAZ)


def yorum_gorseli(y: dict) -> str:
    img, d = _zemin(y["slug"])
    _ust_baslik(d)
    _rozet(d, 340, y["platform"])
    _yildizlar(d, W // 2, 480)

    # buyuk tirnak isareti
    d.text((90, 540), "\u201C", font=_bold(220), fill=(46, 224, 208, 70))

    # yorum metni
    f = _bold(58)
    satirlar = _sar(d, y["metin"], f, W - 220, maxsatir=6)
    if len(satirlar) <= 2:
        f = _bold(66)
        satirlar = _sar(d, y["metin"], f, W - 220, maxsatir=6)
    yy = 760
    for s in satirlar:
        tw = d.textlength(s, font=f)
        d.text(((W - tw) / 2, yy), s, font=f, fill=BEYAZ)
        yy += int(f.size * 1.35)

    # kaynak
    f2 = _normal(36)
    tw = d.textlength(y["kaynak"], font=f2)
    d.text(((W - tw) / 2, yy + 40), y["kaynak"], font=f2, fill=GRI)

    # urun kutusu
    f3 = _bold(40)
    satir2 = _sar(d, y["urun"], f3, W - 320, maxsatir=2)
    kut_h = 90 + (len(satir2) - 1) * 54
    ky = H - 480
    d.rounded_rectangle([120, ky, W - 120, ky + kut_h], radius=24, fill=ZEMIN_ACIK,
                        outline=(46, 224, 208, 120), width=2)
    ty = ky + 24
    for s in satir2:
        tw = d.textlength(s, font=f3)
        d.text(((W - tw) / 2, ty), s, font=f3, fill=TURKUAZ)
        ty += 54

    _alt_bilgi(d)

    yol = os.path.join(CIKTI, f"hikaye-{y['slug']}.png")
    img.save(yol)
    return yol


def kapak_gorseli() -> str:
    img, d = _zemin("yorum-kapak")
    _ust_baslik(d)
    _yildizlar(d, W // 2, 420, adet=5, boy=64)

    f = _bold(72)
    for i, satir in enumerate(["Gerçek müşteri", "yorumlarımız"]):
        tw = d.textlength(satir, font=f)
        d.text(((W - tw) / 2, 560 + i * 100), satir, font=f, fill=BEYAZ)

    # puan kartlari
    kartlar = [("TRENDYOL", "9.3", "Satıcı Puanı"),
               ("HEPSİBURADA", "9.9", "Mağaza Puanı")]
    ky = 880
    for ad, puan, etiket in kartlar:
        d.rounded_rectangle([120, ky, W - 120, ky + 220], radius=28, fill=ZEMIN_ACIK,
                            outline=(46, 224, 208, 120), width=2)
        f1 = _bold(40)
        d.text((170, ky + 45), ad, font=f1, fill=TURUNCU)
        f2 = _normal(32)
        d.text((170, ky + 115), etiket, font=f2, fill=GRI)
        f3 = _bold(96)
        tw = d.textlength(puan, font=f3)
        d.text((W - 170 - tw, ky + 55), puan, font=f3, fill=TURKUAZ)
        ky += 270

    f4 = _normal(36)
    metin = "Kaydır, yorumları gör →"
    tw = d.textlength(metin, font=f4)
    d.text(((W - tw) / 2, ky + 30), metin, font=f4, fill=GRI)

    _alt_bilgi(d)
    yol = os.path.join(CIKTI, "hikaye-yorum-kapak.png")
    img.save(yol)
    return yol


if __name__ == "__main__":
    os.makedirs(CIKTI, exist_ok=True)
    print(kapak_gorseli())
    for y in YORUMLAR:
        print(yorum_gorseli(y))
