# -*- coding: utf-8 -*-
"""Öne çıkarılan hikaye başlıkları için ürün hikayeleri üretir.

Aydınlık satış temalı 1080x1920 görseller: kategori etiketi, beyaz kartta
ürün fotoğrafı, madde listesi, turuncu CTA. Instagram'da paylaşıldıktan
sonra ilgili "öne çıkarılan" başlığının altına sabitlenmek için tasarlandı.

Kullanım: python tools/urun_hikaye_uret.py
Çıktı:   posts/media/hikaye/hikaye-<slug>.png
"""
import io
import os
import random
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from PIL import Image, ImageDraw
from src.carousel_gorsel import (
    SITE, MARKA, _bold, _normal, _sar, _devre_izi,
    _aralikli, _aralikli_genislik,
)

W, H = 1080, 1920
CIKTI = os.path.join(REPO, "posts", "media", "hikaye")

GRADYAN_UST = (208, 238, 243)
GRADYAN_ALT = (250, 252, 254)
KOYU = (11, 20, 32)
TEAL = (0, 150, 136)
TURUNCU = (255, 106, 40)
GRI = (96, 112, 128)
KART = (255, 255, 255)
KART_KENAR = (0, 150, 136, 90)

CDN = "https://cdn.shopify.com/s/files/1/0801/9692/7717/files/"

HIKAYELER = [
    # --- SETLER ---
    dict(slug="set-88-parca", kategori="ARDUINO SETLERİ",
         baslik="Arduino İleri Seviye Set - 88 Parça",
         foto="ileri88.png",
         maddeler=["Uno R3 + 12V adaptör", "Sensör, motor ve LCD grubu",
                   "Kutulu tam set - kod desteği bizden"]),
    dict(slug="set-56-parca", kategori="ARDUINO SETLERİ",
         baslik="Arduino Proje Geliştirme Seti - 56 Parça",
         foto="ortaseviye.png",
         maddeler=["Uno R3 + RFID + IR kumanda", "Servo, sensör ve modüller",
                   "Kendi projeni geliştir"]),
    dict(slug="set-endustriyel", kategori="ARDUINO SETLERİ",
         baslik="Endüstriyel Elektronik Eğitim Seti",
         foto="EndElkhepsi.webp",
         maddeler=["11. sınıf dersine tam uyumlu", "Güç elektroniği + sensörler",
                   "Laboratuvar uygulamalarına hazır"]),
    # --- ROBOTİK ---
    dict(slug="robot-2wd", kategori="ROBOTİK KİTLER",
         baslik="2WD Robot Araba Kiti",
         foto="2wdrobotkiti.png",
         maddeler=["Şasi + motorlar + tekerlekler", "Arduino projelerine hazır",
                   "Montajı kolay, demonte gövde"]),
    dict(slug="robot-3u1", kategori="ROBOTİK KİTLER",
         baslik="3'ü 1 Arada Robot Araba Kiti",
         foto="3lurobot_728225af-7134-4491-bc44-60025f8c9a4f.png",
         maddeler=["Bluetooth + IR + engelden kaçan", "Tek kitte 3 proje",
                   "Kod desteği bizden"]),
    dict(slug="robot-engelden", kategori="ROBOTİK KİTLER",
         baslik="Engelden Kaçan Robot Kiti",
         foto="engeldenkacan.png",
         maddeler=["HC-SR04 + servo tarama", "Uno R3 + L298N dahil",
                   "Kur, kodla, çalıştır"]),
    # --- DEFTERLER ---
    dict(slug="defter-is-dosyasi", kategori="OKUL DEFTERLERİ",
         baslik="İşletmelerde Meslek Eğitimi İş Dosyası",
         foto="isdosyasi1_377200c3-0c47-452a-9bde-8c9dcd1ac333.webp",
         maddeler=["64 sayfa - tel dikiş", "MESEM ve staj öğrencisine",
                   "Tekli veya sınıf paketi"]),
    dict(slug="defter-temrin", kategori="OKUL DEFTERLERİ",
         baslik="Atölye Temrin Defteri",
         foto="1.webp",
         maddeler=["96 sayfa - tel dikiş", "Bir yıl yeter",
                   "Tekli veya sınıf paketi"]),
    dict(slug="defter-sinif-paketi", kategori="OKUL DEFTERLERİ",
         baslik="Sınıf Paketleri - 10 / 20 / 30 Adet",
         foto="isdosyasi1_377200c3-0c47-452a-9bde-8c9dcd1ac333.webp",
         maddeler=["Okullara proforma fatura", "Havale/EFT ile ödeme",
                   "1.200 TL üzeri kargo bedava"]),
    # --- KAMPANYA ---
    dict(slug="kampanya-atolye10", kategori="KAMPANYA",
         baslik="İlk siparişe %10 indirim",
         foto=None, buyuk="ATOLYE10",
         maddeler=["Sepette kodu yaz: ATOLYE10", "Tüm ürünlerde geçerli",
                   "1.200 TL üzeri kargo bedava"]),
]

# Öne çıkarılan kapak görselleri (telefon galerisinden kapak seçmek için)
KAPAKLAR = [
    ("kapak-setler", "SET", (0, 150, 136), (0, 200, 178)),
    ("kapak-robotik", "ROBOT", (255, 106, 40), (255, 160, 70)),
    ("kapak-defterler", "DEFTER", (40, 160, 75), (90, 205, 125)),
    ("kapak-yorumlar", "YORUM", (235, 160, 15), (255, 205, 70)),
    ("kapak-kampanya", "%10", (226, 55, 68), (255, 115, 65)),
    ("kapak-siparis", "SİPARİŞ", (23, 110, 200), (70, 165, 245)),
]


def _zemin(slug):
    img = Image.new("RGB", (W, H), GRADYAN_ALT)
    d = ImageDraw.Draw(img, "RGBA")
    for y in range(H):
        t = min(1.0, y / (H * 0.62))
        renk = tuple(int(GRADYAN_UST[i] + (GRADYAN_ALT[i] - GRADYAN_UST[i]) * t)
                     for i in range(3))
        d.line([(0, y), (W, y)], fill=renk)
    rnd = random.Random(sum(map(ord, slug)))
    _devre_izi(d, rnd, (60, 40, W - 60, 165), adet=5)
    _devre_izi(d, rnd, (50, H - 200, 280, H - 50), adet=2)
    _devre_izi(d, rnd, (W - 280, H - 200, W - 50, H - 50), adet=2)
    return img, d


def _cta(d, cy, metin="Sipariş ver"):
    f = _bold(44)
    tw = d.textlength(metin, font=f)
    x0 = (W - tw) / 2 - 56
    x1 = (W + tw) / 2 + 56
    d.rounded_rectangle([x0, cy - 52, x1, cy + 52], radius=52, fill=TURUNCU)
    d.text(((W - tw) / 2, cy - 22), metin, font=f, fill=(255, 255, 255))
    f2 = _bold(40)
    tw2 = d.textlength(SITE, font=f2)
    d.text(((W - tw2) / 2, cy + 78), SITE, font=f2, fill=KOYU)


def _foto_indir(ad):
    veri = urllib.request.urlopen(CDN + ad, timeout=30).read()
    return Image.open(io.BytesIO(veri)).convert("RGB")


def hikaye(h):
    img, d = _zemin(h["slug"])

    f = _bold(38)
    gw = _aralikli_genislik(d, h["kategori"], f, aralik=6)
    _aralikli(d, ((W - gw) / 2, 200), h["kategori"], f, TEAL, aralik=6)

    y = 300
    if h.get("foto"):
        # beyaz kartta urun fotografi
        kart = [110, y, W - 110, y + 620]
        d.rounded_rectangle(kart, radius=36, fill=KART, outline=KART_KENAR, width=2)
        foto = _foto_indir(h["foto"])
        foto.thumbnail((W - 320, 540))
        img.paste(foto, (int((W - foto.width) / 2), int(y + (620 - foto.height) / 2)))
        y += 620 + 60
    elif h.get("buyuk"):
        # kampanya: kod rozeti
        f0 = _bold(150)
        tw = d.textlength("%10", font=f0)
        d.text(((W - tw) / 2, y + 60), "%10", font=f0, fill=TURUNCU)
        fk = _bold(72)
        kod = h["buyuk"]
        tw = d.textlength(kod, font=fk)
        kx0 = (W - tw) / 2 - 60
        kx1 = (W + tw) / 2 + 60
        d.rounded_rectangle([kx0, y + 300, kx1, y + 430], radius=30,
                            fill=KOYU)
        d.text(((W - tw) / 2, y + 328), kod, font=fk, fill=(255, 200, 60))
        y += 520
    else:
        y += 140

    f1 = _bold(64)
    for s in _sar(d, h["baslik"], f1, W - 200, maxsatir=3):
        tw = d.textlength(s, font=f1)
        d.text(((W - tw) / 2, y), s, font=f1, fill=KOYU)
        y += 86
    y += 40

    f2 = _normal(46)
    for m in h["maddeler"]:
        d.ellipse([200, y + 18, 224, y + 42], fill=TEAL)
        d.text((260, y), m, font=f2, fill=KOYU)
        y += 78

    _cta(d, H - 380)
    f3 = _bold(36)
    tw = d.textlength(MARKA, font=f3)
    d.text(((W - tw) / 2, H - 130), MARKA, font=f3, fill=GRI)

    yol = os.path.join(CIKTI, f"hikaye-{h['slug']}.png")
    img.save(yol)
    print("✅", yol)


def kapak(slug, etiket, renk1, renk2):
    """Canlı, kategori renkli kapak — IG öne çıkarılan kapağı ortadan kırpar."""
    img = Image.new("RGB", (W, H), GRADYAN_ALT)
    d = ImageDraw.Draw(img, "RGBA")
    # zemin: acik turkuaz gradyan (hikayelerle ayni aile)
    for y in range(H):
        t = min(1.0, y / (H * 0.7))
        renk = tuple(int(GRADYAN_UST[i] + (GRADYAN_ALT[i] - GRADYAN_UST[i]) * t)
                     for i in range(3))
        d.line([(0, y), (W, y)], fill=renk)
    # ortada dikey gradyanli dolu renk dairesi
    r = 340
    cx, cy = W // 2, H // 2
    daire = Image.new("RGB", (2 * r, 2 * r))
    dd = ImageDraw.Draw(daire)
    for yy in range(2 * r):
        t = yy / (2 * r)
        dd.line([(0, yy), (2 * r, yy)],
                fill=tuple(int(renk1[i] + (renk2[i] - renk1[i]) * t) for i in range(3)))
    maske = Image.new("L", (2 * r, 2 * r), 0)
    ImageDraw.Draw(maske).ellipse([0, 0, 2 * r, 2 * r], fill=255)
    # yumusak golge
    d.ellipse([cx - r + 14, cy - r + 26, cx + r + 14, cy + r + 26],
              fill=(11, 20, 32, 45))
    img.paste(daire, (cx - r, cy - r), maske)
    # ince beyaz halka
    d.ellipse([cx - r + 16, cy - r + 16, cx + r - 16, cy + r - 16],
              outline=(255, 255, 255, 230), width=8)
    boy = 104 if len(etiket) <= 5 else 76
    f = _bold(boy)
    tw = d.textlength(etiket, font=f)
    d.text((cx - tw / 2 + 3, cy - boy * 0.62 + 3), etiket, font=f,
           fill=(0, 0, 0, 60))
    d.text((cx - tw / 2, cy - boy * 0.62), etiket, font=f, fill=(255, 255, 255))
    yol = os.path.join(CIKTI, f"hikaye-{slug}.png")
    img.save(yol)
    print("✅", yol)


if __name__ == "__main__":
    os.makedirs(CIKTI, exist_ok=True)
    for h in HIKAYELER:
        hikaye(h)
    for slug, etiket, r1, r2 in KAPAKLAR:
        kapak(slug, etiket, r1, r2)
