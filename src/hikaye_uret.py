# -*- coding: utf-8 -*-
"""Her gün taze Instagram hikayesi üretir ve yayınlar.

Kataloğdan daha önce hikayesi atılmamış ürünleri seçer, satış odaklı
aydınlık temada görsel üretir (gün aşırı iki şablon: ürün tanıtımı /
fiyat kartı) ve Instagram'a hikaye olarak yükler. İşlenen ürünler
state/hikaye_seen.json'da tutulur; havuz bitince tur başa döner.

Kullanım:
    python -m src.hikaye_uret --adet 2             # üret + yayınla
    python -m src.hikaye_uret --adet 4 --onizleme  # sadece üret
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import pathlib
import random
import urllib.request

from PIL import Image, ImageDraw

from .carousel_gorsel import (
    SITE, MARKA, _bold, _normal, _sar, _devre_izi,
    _aralikli, _aralikli_genislik,
)
from .shopify_source import fetch_products, ozet

W, H = 1080, 1920
STATE_PATH = pathlib.Path("state/hikaye_seen.json")
CIKTI_DIR = pathlib.Path("posts/media/hikaye/gunluk")
MANIFEST_PATH = CIKTI_DIR / "manifest.json"

GRADYAN_UST = (208, 238, 243)
GRADYAN_ALT = (250, 252, 254)
KOYU = (11, 20, 32)
TEAL = (0, 150, 136)
TURUNCU = (255, 106, 40)
GRI = (96, 112, 128)
KART = (255, 255, 255)
KART_KENAR = (0, 150, 136, 90)


def _etiket(urun: dict) -> str:
    """Kullanıcının öne çıkarılan başlığına denk düşen kategori etiketi."""
    ad = (urun.get("title") or "").lower()
    if "defter" in ad or "dosya" in ad:
        return "OKUL DEFTERLERİ"
    if "robot" in ad:
        return "ROBOTİK KİTLER"
    if "arduino" in ad:
        return "ARDUINO SETLERİ"
    if any(k in ad for k in ("havya", "pense", "tornavida", "alet", "lehim")):
        return "EL ALETLERİ"
    if "set" in ad or "kit" in ad:
        return "SETLER"
    return "GÜNÜN ÜRÜNÜ"


def _tl(deger) -> str:
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return ""
    tam = f"{int(sayi):,}".replace(",", ".")
    kurus = round((sayi - int(sayi)) * 100)
    return f"{tam},{kurus:02d} ₺" if kurus else f"{tam} ₺"


def _zemin(slug: str):
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


def _kategori(d, metin: str) -> None:
    f = _bold(38)
    gw = _aralikli_genislik(d, metin, f, aralik=6)
    _aralikli(d, ((W - gw) / 2, 200), metin, f, TEAL, aralik=6)


def _foto_kart(img, d, url: str, y: int, yukseklik: int = 560) -> int:
    d.rounded_rectangle([110, y, W - 110, y + yukseklik], radius=36,
                        fill=KART, outline=KART_KENAR, width=2)
    veri = urllib.request.urlopen(url, timeout=30).read()
    foto = Image.open(io.BytesIO(veri)).convert("RGB")
    foto.thumbnail((W - 320, yukseklik - 80))
    img.paste(foto, (int((W - foto.width) / 2),
                     int(y + (yukseklik - foto.height) / 2)))
    return y + yukseklik


def _baslik(d, metin: str, y: int, maxsatir: int = 3) -> int:
    """Başlığı ASLA kesmez: sığana kadar puntoyu küçültür.

    Kes-at yaklaşımı "...Robot Ar..." gibi yarım ürün adı bırakıyordu
    (20.08 geri bildirimi). Uzun adlarda önce " - " / "(" ayracından
    sadeleştirir, sonra 62'den 40'a kadar punto düşürür.
    """
    kisa = metin
    for ayrac in (" - ", " — ", " ("):
        if len(kisa) > 42 and ayrac in kisa:
            kisa = kisa.split(ayrac)[0].strip()
            break
    for boyut in (62, 56, 50, 44, 40):
        f = _bold(boyut)
        satirlar = _sar(d, kisa, f, W - 180, maxsatir=maxsatir + 2)
        if len(satirlar) <= maxsatir and not any(s.endswith("...") for s in satirlar):
            break
    for satir in satirlar[:maxsatir]:
        tw = d.textlength(satir, font=f)
        d.text(((W - tw) / 2, y), satir, font=f, fill=KOYU)
        y += int(boyut * 1.35)
    return y


def _cta(d, cy: int, metin: str = "Sipariş ver") -> None:
    f = _bold(44)
    tw = d.textlength(metin, font=f)
    d.rounded_rectangle([(W - tw) / 2 - 56, cy - 52, (W + tw) / 2 + 56, cy + 52],
                        radius=52, fill=TURUNCU)
    d.text(((W - tw) / 2, cy - 22), metin, font=f, fill=(255, 255, 255))
    f2 = _bold(40)
    tw2 = d.textlength(SITE, font=f2)
    d.text(((W - tw2) / 2, cy + 78), SITE, font=f2, fill=KOYU)


def _marka(d) -> None:
    f = _bold(36)
    tw = d.textlength(MARKA, font=f)
    d.text(((W - tw) / 2, H - 130), MARKA, font=f, fill=GRI)


def _aciklama_hazirla(d, metin: str, genislik: int, maxsatir: int):
    """Açıklamayı emoji'siz, TAM CÜMLE ve kesintisiz döndürür.

    Sığmıyorsa önce cümle atar, yetmezse puntoyu düşürür — "2'li 18650
    Li-..." gibi yarım metin çıkmaz (20.08 geri bildirimi).
    """
    metin = "".join(ch for ch in metin if ord(ch) < 0x2500).strip()
    cumleler = [c.strip() for c in metin.replace("!", ".").split(".") if c.strip()]
    if not cumleler:
        return _normal(44), []
    for boyut in (44, 40, 36):
        f = _normal(boyut)
        secili = ""
        for c in cumleler:
            aday = (secili + " " + c).strip() + "."
            satirlar = _sar(d, aday, f, genislik, maxsatir=maxsatir + 2)
            if len(satirlar) > maxsatir or any(x.endswith("...") for x in satirlar):
                break
            secili = aday
        if secili:
            return f, _sar(d, secili, f, genislik, maxsatir=maxsatir)
    # tek cumle bile sigmadi: en kucuk puntoyla ilk cumleyi ver
    f = _normal(36)
    return f, _sar(d, cumleler[0] + ".", f, genislik, maxsatir=maxsatir)


def hikaye_tanitim(urun: dict, cikti: pathlib.Path) -> None:
    """Şablon A: ürün fotoğrafı + kısa açıklama."""
    img, d = _zemin(urun["handle"])
    _kategori(d, _etiket(urun))
    alt = _foto_kart(img, d, urun["images"][0]["src"], 300)
    y = _baslik(d, urun["title"], alt + 60)
    metin = ozet(urun.get("body_html", ""))
    f, satirlar = _aciklama_hazirla(d, metin, W - 260, maxsatir=3)
    for satir in satirlar:
        tw = d.textlength(satir, font=f)
        d.text(((W - tw) / 2, y + 20), satir, font=f, fill=GRI)
        y += int(f.size * 1.4)
    _cta(d, H - 380)
    _marka(d)
    img.save(cikti)


def hikaye_fiyat(urun: dict, cikti: pathlib.Path) -> None:
    """Şablon B: ürün fotoğrafı + fiyat + indirim kodu."""
    img, d = _zemin(urun["handle"] + "f")
    _kategori(d, _etiket(urun))
    alt = _foto_kart(img, d, urun["images"][0]["src"], 300)
    y = _baslik(d, urun["title"], alt + 50)
    fiyat = _tl((urun.get("variants") or [{}])[0].get("price"))
    if fiyat:
        f = _bold(110)
        tw = d.textlength(fiyat, font=f)
        d.text(((W - tw) / 2, y + 30), fiyat, font=f, fill=TURUNCU)
        y += 190
    f2 = _bold(44)
    kod = "ATOLYE10 ile sepette %10 indirim"
    tw = d.textlength(kod, font=f2)
    d.rounded_rectangle([(W - tw) / 2 - 40, y + 10, (W + tw) / 2 + 40, y + 96],
                        radius=26, fill=KOYU)
    d.text(((W - tw) / 2, y + 30), kod, font=f2, fill=(255, 200, 60))
    _cta(d, H - 380)
    _marka(d)
    img.save(cikti)


def _seen_oku() -> list[str]:
    if not STATE_PATH.exists():
        return []
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _seen_yaz(seen: list[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(seen, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")


def uret(adet: int = 2, onizleme: bool = False) -> int:
    urunler = [u for u in fetch_products() if u.get("images")]
    seen = _seen_oku()
    aday = [u for u in urunler if str(u["id"]) not in seen]
    if len(aday) < adet:
        print("Havuz bitti, tur başa dönüyor.")
        seen = []
        aday = urunler
    # Cesitlilik: pahali/zengin urunler one gelsin diye fotograf sayisina gore
    # sirala, ayni gunun ikilisi farkli kategorilerden secilsin.
    aday.sort(key=lambda u: len(u.get("images") or []), reverse=True)
    secilen: list[dict] = []
    for u in aday:
        if len(secilen) >= adet:
            break
        if any(_etiket(u) == _etiket(s) for s in secilen):
            continue
        secilen.append(u)
    for u in aday:  # kategori cesitliligi yetmezse kalanlarla doldur
        if len(secilen) >= adet:
            break
        if u not in secilen:
            secilen.append(u)

    CIKTI_DIR.mkdir(parents=True, exist_ok=True)
    # 7 gunden eski gorselleri temizle (repo sismesin)
    esik = dt.date.today() - dt.timedelta(days=7)
    for eski in CIKTI_DIR.glob("hikaye-*.png"):
        try:
            tarih = dt.datetime.strptime(eski.stem.split("-")[1], "%Y%m%d").date()
            if tarih < esik:
                eski.unlink()
        except (ValueError, IndexError):
            continue

    gun = dt.date.today().toordinal()
    manifest = []
    for i, u in enumerate(secilen):
        yol = CIKTI_DIR / f"hikaye-{dt.date.today():%Y%m%d}-{i+1}.png"
        sablon = hikaye_tanitim if (gun + i) % 2 == 0 else hikaye_fiyat
        sablon(u, yol)
        print(f"🖼️  {yol} ← {u['title'][:60]} [{_etiket(u)}]")
        manifest.append({"dosya": str(yol).replace("\\", "/"),
                         "urun_id": str(u["id"]), "urun": u["title"]})
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    # 21.08 sonrasi hikayeleri kullanici elle paylasiyor, yayinla evresi
    # kosmuyor; kaydi burada tutmazsak her gun ayni urunler secilir.
    if not onizleme:
        for kayit in manifest:
            if kayit["urun_id"] not in seen:
                seen.append(kayit["urun_id"])
        _seen_yaz(seen)
    return 0


def yayinla() -> int:
    """Manifestteki (repoya itilmis) gorselleri hikaye olarak yayinlar.

    Iki evre gerekli cunku Instagram Graph API gorseli herkese acik URL'den
    ceker; dosya once commit'lenip raw URL kazanmali (20.08 dersi).
    """
    from . import instagram

    if not MANIFEST_PATH.exists():
        print("Manifest yok — once --evre uret calistir.")
        return 1
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    seen = _seen_oku()
    hata = 0
    for kayit in manifest:
        try:
            kimlik = instagram.hikaye_yayinla(kayit["dosya"])
            print(f"✅ hikaye yayınlandı: {kayit['urun'][:50]} (id: {kimlik})")
            if kayit["urun_id"] not in seen:
                seen.append(kayit["urun_id"])
        except Exception as exc:  # noqa: BLE001
            hata += 1
            print(f"❌ hikaye yayınlanamadı: {exc}")
    _seen_yaz(seen)
    return 1 if hata else 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adet", type=int, default=2)
    p.add_argument("--evre", choices=["uret", "yayinla"], default=None,
                   help="CI iki evrede kosar: uret (dosya+manifest) sonra yayinla")
    p.add_argument("--onizleme", action="store_true",
                   help="uret ile ayni: yayinlamadan gorselleri uret")
    a = p.parse_args()
    if a.evre == "yayinla":
        raise SystemExit(yayinla())
    raise SystemExit(uret(a.adet, a.onizleme))


if __name__ == "__main__":
    main()
