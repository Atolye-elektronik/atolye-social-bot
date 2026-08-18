# -*- coding: utf-8 -*-
"""Trendyol/Hepsiburada yorumlarindan 1080x1920 hikaye gorselleri uretir.

Aydinlik, satis odakli tema: acik zemin, koyu metin, turuncu CTA butonu.

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
    ALTIN, SITE, MARKA, _bold, _normal, _sar, _devre_izi,
    _aralikli, _aralikli_genislik,
)

W, H = 1080, 1920
CIKTI = os.path.join(REPO, "posts", "media", "hikaye")

# Acik tema renkleri
GRADYAN_UST = (208, 238, 243)          # acik turkuaz
GRADYAN_ALT = (250, 252, 254)          # beyaza yakin
KOYU = (11, 20, 32)                    # metin — koyu lacivert
TEAL = (0, 150, 136)                   # acik zeminde okunur turkuaz
TURUNCU = (255, 106, 40)
GRI = (96, 112, 128)
KART = (255, 255, 255)
KART_KENAR = (0, 150, 136, 90)

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
    img = Image.new("RGB", (W, H), GRADYAN_ALT)
    d = ImageDraw.Draw(img, "RGBA")
    # dikey gradyan: ustte acik turkuaz, asagida beyaz
    for y in range(H):
        t = min(1.0, y / (H * 0.62))
        renk = tuple(int(GRADYAN_UST[i] + (GRADYAN_ALT[i] - GRADYAN_UST[i]) * t)
                     for i in range(3))
        d.line([(0, y), (W, y)], fill=renk)
    # soluk devre izleri: canli zemini bozmasinlar diye sadece ust/alt seritte
    rnd = random.Random(sum(map(ord, slug)))
    _devre_izi(d, rnd, (60, 40, W - 60, 165), adet=5)
    # altta yalnizca kenarlara iz koy — marka yazisiyla cakismasin
    _devre_izi(d, rnd, (50, H - 200, 280, H - 50), adet=2)
    _devre_izi(d, rnd, (W - 280, H - 200, W - 50, H - 50), adet=2)
    return img, d


def _ust_baslik(d: ImageDraw.ImageDraw) -> None:
    f = _bold(38)
    metin = "MÜŞTERİLERİMİZ NE DİYOR?"
    gw = _aralikli_genislik(d, metin, f, aralik=6)
    _aralikli(d, ((W - gw) / 2, 210), metin, f, TEAL, aralik=6)


def _yildizlar(d: ImageDraw.ImageDraw, cx: int, y: int, adet: int = 5, boy: int = 52) -> None:
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
    d.rounded_rectangle([x0, cy - 38, x1, cy + 38], radius=38, fill=KART,
                        outline=TURUNCU, width=3)
    d.text(((W - tw) / 2, cy - 24), metin, font=f, fill=TURUNCU)


def _cta(d: ImageDraw.ImageDraw, cy: int, metin: str = "Sen de sipariş ver") -> None:
    """Turuncu dolu CTA butonu + altinda site adresi."""
    f = _bold(44)
    tw = d.textlength(metin, font=f)
    pad_x = 56
    x0 = (W - tw) / 2 - pad_x
    x1 = (W + tw) / 2 + pad_x
    d.rounded_rectangle([x0, cy - 52, x1, cy + 52], radius=52, fill=TURUNCU)
    d.text(((W - tw) / 2, cy - 22), metin, font=f, fill=(255, 255, 255))
    f2 = _bold(40)
    tw2 = d.textlength(SITE, font=f2)
    d.text(((W - tw2) / 2, cy + 78), SITE, font=f2, fill=KOYU)


def _alt_marka(d: ImageDraw.ImageDraw) -> None:
    f1 = _bold(36)
    tw = d.textlength(MARKA, font=f1)
    d.text(((W - tw) / 2, H - 130), MARKA, font=f1, fill=GRI)


def yorum_gorseli(y: dict) -> str:
    img, d = _zemin(y["slug"])
    _ust_baslik(d)
    _rozet(d, 340, y["platform"])
    _yildizlar(d, W // 2, 480)

    # buyuk tirnak isareti
    d.text((90, 540), "“", font=_bold(220), fill=(0, 150, 136, 60))

    # yorum karti
    f = _bold(56)
    satirlar = _sar(d, y["metin"], f, W - 300, maxsatir=6)
    if len(satirlar) <= 2:
        f = _bold(64)
        satirlar = _sar(d, y["metin"], f, W - 300, maxsatir=6)
    sat_h = int(f.size * 1.35)
    kart_h = len(satirlar) * sat_h + 170
    ky = 700
    d.rounded_rectangle([90, ky, W - 90, ky + kart_h], radius=36, fill=KART,
                        outline=KART_KENAR, width=2)
    yy = ky + 60
    for s in satirlar:
        tw = d.textlength(s, font=f)
        d.text(((W - tw) / 2, yy), s, font=f, fill=KOYU)
        yy += sat_h
    f2 = _normal(34)
    tw = d.textlength(y["kaynak"], font=f2)
    d.text(((W - tw) / 2, yy + 26), y["kaynak"], font=f2, fill=GRI)

    # urun adi
    f3 = _bold(40)
    satir2 = _sar(d, y["urun"], f3, W - 240, maxsatir=2)
    ty = ky + kart_h + 56
    for s in satir2:
        tw = d.textlength(s, font=f3)
        d.text(((W - tw) / 2, ty), s, font=f3, fill=TEAL)
        ty += 54

    _cta(d, H - 400)
    _alt_marka(d)

    yol = os.path.join(CIKTI, f"hikaye-{y['slug']}.png")
    img.save(yol)
    return yol


def kapak_gorseli() -> str:
    img, d = _zemin("yorum-kapak")
    _ust_baslik(d)
    _yildizlar(d, W // 2, 420, adet=5, boy=64)

    f = _bold(76)
    for i, satir in enumerate(["Gerçek müşteri", "yorumlarımız"]):
        tw = d.textlength(satir, font=f)
        d.text(((W - tw) / 2, 540 + i * 104), satir, font=f, fill=KOYU)

    kartlar = [("TRENDYOL", "9.3", "Satıcı Puanı"),
               ("HEPSİBURADA", "9.9", "Mağaza Puanı")]
    ky = 860
    for ad, puan, etiket in kartlar:
        d.rounded_rectangle([120, ky, W - 120, ky + 210], radius=28, fill=KART,
                            outline=KART_KENAR, width=2)
        f1 = _bold(40)
        d.text((170, ky + 42), ad, font=f1, fill=TURUNCU)
        f2 = _normal(32)
        d.text((170, ky + 110), etiket, font=f2, fill=GRI)
        f3 = _bold(96)
        tw = d.textlength(puan, font=f3)
        d.text((W - 170 - tw, ky + 50), puan, font=f3, fill=TEAL)
        ky += 260

    f4 = _normal(36)
    metin = "Kaydır, yorumları gör →"
    tw = d.textlength(metin, font=f4)
    d.text(((W - tw) / 2, ky + 20), metin, font=f4, fill=GRI)

    _cta(d, H - 400)
    _alt_marka(d)
    yol = os.path.join(CIKTI, "hikaye-yorum-kapak.png")
    img.save(yol)
    return yol


if __name__ == "__main__":
    os.makedirs(CIKTI, exist_ok=True)
    print(kapak_gorseli())
    for y in YORUMLAR:
        print(yorum_gorseli(y))
