# -*- coding: utf-8 -*-
"""Resmi bayram ve anma gunleri icin post + hikaye gorseli uretir.

Iki ton var ve karistirilmaz:

  kutlama -> 23 Nisan, 1 Mayis, 19 Mayis, 30 Agustos, 29 Ekim, dini bayramlar
             Bayrak kirmizisi zemin, "KUTLU OLSUN".
  anma    -> 10 Kasim, 15 Temmuz
             Koyu lacivert zemin, "SAYGIYLA ANIYORUZ". Kutlama dili YOK,
             hashtag YOK.

Hicbirinde fiyat, urun gorseli, indirim kodu veya satis cagrisi yer almaz.
Bayram gununde satis yapan marka kotu gorunur; kazanc da yoktur.

Kullanim:
    python -m tools.bayram_gorsel --tarih 2026-08-30          # gorseller
    python -m tools.bayram_gorsel --tarih 2026-08-30 --post   # + kuyruga post
    python -m tools.bayram_gorsel --liste                     # yaklasanlari gor
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import pathlib
import random
import sys
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.carousel_gorsel import SITE, MARKA, _bold, _normal, _sar, _aralikli, _aralikli_genislik  # noqa: E402

TZ = ZoneInfo("Europe/Istanbul")
VERI = pathlib.Path("content/bayramlar.json")
CIKTI = pathlib.Path("posts/media/bayram")
LOGO = pathlib.Path("posts/media/marka/logo.png")
POSTS = pathlib.Path("posts")

POST_BOYUT = (1080, 1350)
HIKAYE_BOYUT = (1080, 1920)

# Bayrak kirmizisi: TS 1988 / Turk Bayragi Tuzugu tonu.
KIRMIZI = (227, 10, 23)
KIRMIZI_KOYU = (150, 6, 15)
# Kutlamada zemin AYDINLIK: bayrak kirmizi oldugu icin kirmizi zeminde kaybolur.
ACIK_UST = (255, 255, 255)
ACIK_ALT = (236, 239, 244)
# Anma gunleri icin: kutlama cagrisimi olmayan koyu lacivert.
LACIVERT = (14, 22, 38)
LACIVERT_KOYU = (7, 11, 20)
BEYAZ = (255, 255, 255)
KOYU_METIN = (16, 22, 33)


def _buyuk(s: str) -> str:
    """Turkce-dogru buyuk harf: i -> I DEGIL, i -> I(noktali)."""
    return s.replace("i", "İ").replace("ı", "I").upper()


# ---------------------------------------------------------------- ay-yildiz

def _yildiz(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float,
            renk, aci: float = -90.0) -> None:
    """Bes koseli yildiz. r = dis yaricap."""
    ic = r * 0.382  # duzgun bes koseli yildizin ic/dis orani
    noktalar = []
    for i in range(10):
        yaricap = r if i % 2 == 0 else ic
        t = math.radians(aci + i * 36)
        noktalar.append((cx + yaricap * math.cos(t), cy + yaricap * math.sin(t)))
    d.polygon(noktalar, fill=renk)


def turk_bayragi(yukseklik: int) -> Image.Image:
    """Turk Bayragi - Turk Bayragi Tuzugu'ndeki resmi oranlarla.

    G = bayrak yuksekligi kabul edilirse:
      * boy               = 1.5 G
      * dis daire capi    = 0.5 G   , merkez (0.500 G, 0.5 G)
      * ic daire capi     = 0.4 G   , merkez (0.5625 G, 0.5 G)   [G/16 kaydirma]
      * yildiz cevrel capi= 0.25 G  , ic dairenin sag ucundan G/16 bosluk
      * yildizin bir ucu hilale (sola) bakar

    Goz karari cizilmiyor; ay-yildizin yeri ve buyuklugu tanimli.
    Kenar yumusakligi icin 4x buyuk cizilip kucultuluyor.
    """
    G = yukseklik
    O = 4                                   # supersampling
    g, boy = G * O, int(G * 1.5) * O
    im = Image.new("RGBA", (boy, g), KIRMIZI + (255,))
    d = ImageDraw.Draw(im)
    beyaz = (255, 255, 255, 255)

    dis_r = 0.25 * g
    dis_c = (0.50 * g, 0.50 * g)
    ic_r = 0.20 * g
    ic_c = (0.5625 * g, 0.50 * g)

    d.ellipse([dis_c[0] - dis_r, dis_c[1] - dis_r,
               dis_c[0] + dis_r, dis_c[1] + dis_r], fill=beyaz)
    # Ic daire zemin rengiyle doldurulunca hilal olusuyor
    d.ellipse([ic_c[0] - ic_r, ic_c[1] - ic_r,
               ic_c[0] + ic_r, ic_c[1] + ic_r], fill=KIRMIZI + (255,))

    yil_r = 0.125 * g                        # cevrel yaricap = 0.25G / 2
    bosluk = g / 16
    yil_cx = (ic_c[0] + ic_r) + bosluk + yil_r
    _yildiz(d, yil_cx, 0.50 * g, yil_r, beyaz, aci=180)   # bir uc sola bakar

    return im.resize((int(boy / O), int(g / O)), Image.LANCZOS)


def _zemin(boyut: tuple[int, int], tur: str) -> Image.Image:
    """Kutlama: aydinlik zemin (bayrak kirmizisi zeminde kaybolur).
    Anma: koyu lacivert, sessiz."""
    w, h = boyut
    ust, alt = (ACIK_UST, ACIK_ALT) if tur == "kutlama" else (LACIVERT, LACIVERT_KOYU)
    im = Image.new("RGBA", boyut, ust + (255,))
    d = ImageDraw.Draw(im)
    for y in range(h):
        k = y / max(1, h - 1)
        d.line([(0, y), (w, y)],
               fill=tuple(int(ust[i] + (alt[i] - ust[i]) * k) for i in range(3)) + (255,))
    return im


def _bayrak_bas(im: Image.Image, merkez_x: int, y: int, genislik: int) -> int:
    """Bayragi golgesiyle basar, alt kenarin y'sini dondurur.

    Bayragin UZERINE yazi yazilmiyor: Turk Bayragi Kanunu bayragin
    uzerine yazi yazilmasini/isaret konulmasini yasakliyor. Bayrak ayri
    bir ogedir, metin altinda durur.
    """
    yuk = int(genislik / 1.5)
    bayrak = turk_bayragi(yuk)
    x = merkez_x - genislik // 2

    golge = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(golge).rectangle([x, y + 6, x + genislik, y + yuk + 6],
                                    fill=(0, 0, 0, 60))
    im.alpha_composite(golge.filter(ImageFilter.GaussianBlur(14)))
    im.alpha_composite(bayrak, (x, y))
    return y + yuk


def _logo_bas(im: Image.Image, merkez_x: int, y: int, cap: int) -> int:
    """Logoyu dairesel maskeyle basar, alt kenarin y'sini dondurur."""
    if not LOGO.exists():
        return y
    logo = Image.open(LOGO).convert("RGBA").resize((cap, cap), Image.LANCZOS)
    maske = Image.new("L", (cap, cap), 0)
    ImageDraw.Draw(maske).ellipse([0, 0, cap - 1, cap - 1], fill=255)
    mevcut = logo.split()[3]
    maske = Image.composite(mevcut, Image.new("L", (cap, cap), 0), maske)
    im.paste(logo, (merkez_x - cap // 2, y), maske)
    return y + cap


def _ortala(d: ImageDraw.ImageDraw, y: int, metin: str, f, renk, w: int) -> int:
    genislik = d.textlength(metin, font=f)
    d.text(((w - genislik) / 2, y), metin, font=f, fill=renk)
    return y + int(f.size * 1.25)


def _ciz(bayram: dict, boyut: tuple[int, int]) -> Image.Image:
    """Post ve hikaye ayni duzeni paylasir, yalniz olcekler degisir."""
    w, h = boyut
    tur = bayram.get("tur", "kutlama")
    im = _zemin(boyut, tur)
    d = ImageDraw.Draw(im)

    hikaye = h > w * 1.4
    kutlama = tur == "kutlama"
    # Hikayede IG arayuzu ust ~%14, alt ~%20 kapatir; post'ta yalniz nefes payi
    ust_sinir = int(h * 0.17) if hikaye else int(h * 0.09)
    alt_sinir = h - (int(h * 0.20) if hikaye else int(h * 0.08))

    # Renkler zemine gore
    c_marka = (90, 100, 116) if kutlama else (255, 255, 255, 190)
    c_tarih = KIRMIZI if kutlama else (255, 255, 255, 235)
    c_ad = KOYU_METIN if kutlama else BEYAZ
    c_slogan = KIRMIZI if kutlama else (255, 255, 255, 235)
    c_site = (120, 130, 146) if kutlama else (255, 255, 255, 190)
    c_ayrac = (206, 212, 222) if kutlama else (255, 255, 255, 120)

    # Alt blok (logo + site) once yer ayirir, ustteki blok kalan alana yerlesir.
    cap = 96 if not hikaye else 108
    fsite = _normal(26 if not hikaye else 28)
    logo_y = alt_sinir - (cap + 16 + int(fsite.size * 1.3))
    _logo_bas(im, w // 2, logo_y, cap)
    _ortala(d, logo_y + cap + 16, SITE, fsite, c_site, w)

    # --- bayrak + metin blogu: once olcup sonra ciziyoruz ki ortalansin ---
    maxw = int(w * 0.84)
    fm = _bold(26 if not hikaye else 28)
    fk = _bold(58 if not hikaye else 64)
    fa = _bold(80 if not hikaye else 88)
    satirlar = _sar(d, _buyuk(bayram["ad"]), fa, maxw, maxsatir=4)
    if len(satirlar) > 2:          # cok uzun ad -> puntoyu dusur
        fa = _bold(64 if not hikaye else 72)
        satirlar = _sar(d, _buyuk(bayram["ad"]), fa, maxw, maxsatir=4)
    fs = _bold(48 if not hikaye else 54)
    slogan = "KUTLU OLSUN" if kutlama else "SAYGIYLA ANIYORUZ"

    bayrak_gen = int(w * 0.42)
    bayrak_yuk = int(bayrak_gen / 1.5)
    AYRAC = 40
    yukseklik = (int(fm.size * 2.4) + bayrak_yuk + 56
                 + int(fk.size * 1.25) + 10 + AYRAC
                 + len(satirlar) * int(fa.size * 1.22) + 34 + int(fs.size * 1.25))

    bosluk = (logo_y - 44) - ust_sinir
    y = ust_sinir + max(0, (bosluk - yukseklik) // 2)

    gen = _aralikli_genislik(d, MARKA, fm, 8)
    _aralikli(d, ((w - gen) / 2, y), MARKA, fm, c_marka, 8)
    y += int(fm.size * 2.4)

    # Bayrak: ayri oge, uzerine yazi yazilmiyor
    y = _bayrak_bas(im, w // 2, y, bayrak_gen) + 56

    y = _ortala(d, y, bayram["kisa"], fk, c_tarih, w)
    y += 10
    d.line([(w * 0.38, y), (w * 0.62, y)], fill=c_ayrac, width=3)
    y += AYRAC

    for s in satirlar:
        y = _ortala(d, y, s, fa, c_ad, w)

    y += 34
    # Ton cumlesi - kutlama ile anma burada ayrisir
    _ortala(d, y, slogan, fs, c_slogan, w)

    return im.convert("RGB")


# ------------------------------------------------------------------- veri

def _yukle() -> list[dict]:
    if not VERI.exists():
        raise SystemExit(f"Bayram dosyasi yok: {VERI}")
    return json.loads(VERI.read_text(encoding="utf-8"))["gunler"]


def _tarih_of(bayram: dict, yil: int) -> dt.date:
    t = bayram["tarih"]
    if len(t) == 10:                       # tam tarih (dini bayramlar)
        return dt.date.fromisoformat(t)
    ay, gun = t.split("-")
    return dt.date(yil, int(ay), int(gun))


def bul(tarih: dt.date) -> dict | None:
    for b in _yukle():
        if _tarih_of(b, tarih.year) == tarih:
            return b
    return None


def yaklasanlar(bugun: dt.date, gun: int = 400) -> list[tuple[dt.date, dict]]:
    cikti = []
    for b in _yukle():
        for yil in (bugun.year, bugun.year + 1):
            try:
                t = _tarih_of(b, yil)
            except ValueError:
                continue
            if bugun <= t <= bugun + dt.timedelta(days=gun):
                cikti.append((t, b))
    cikti.sort(key=lambda p: p[0])
    # dini bayramlarda tam tarih sabit oldugu icin ayni kayit iki kez girmesin
    gorulen, tekil = set(), []
    for t, b in cikti:
        if (t, b["slug"]) in gorulen:
            continue
        gorulen.add((t, b["slug"]))
        tekil.append((t, b))
    return tekil


# ------------------------------------------------------------------ uretim

def uret(bayram: dict, tarih: dt.date) -> tuple[pathlib.Path, pathlib.Path]:
    CIKTI.mkdir(parents=True, exist_ok=True)
    kok = f"{tarih.isoformat()}-{bayram['slug']}"
    p_post = CIKTI / f"{kok}-post.png"
    p_hikaye = CIKTI / f"{kok}-hikaye.png"
    _ciz(bayram, POST_BOYUT).save(p_post, quality=95)
    _ciz(bayram, HIKAYE_BOYUT).save(p_hikaye, quality=95)
    return p_post, p_hikaye


def post_yaz(bayram: dict, tarih: dt.date, medya: pathlib.Path,
             saat: str = "09:00") -> pathlib.Path:
    yol = POSTS / f"{tarih.isoformat()}-bayram-{bayram['slug']}.md"
    if yol.exists():
        print(f"  post zaten var, dokunulmadi: {yol}")
        return yol
    etiket = bayram.get("etiketler", "").strip()
    govde = bayram["metin"].strip()
    if etiket:                      # anma gunlerinde etiket bos birakilir
        govde += f"\n\n{etiket}"
    yol.write_text(
        "---\n"
        "platforms: [instagram, facebook, threads]\n"
        f"media: {medya.as_posix()}\n"
        f"publish_at: {tarih.isoformat()} {saat}\n"
        "---\n"
        f"{govde}\n",
        encoding="utf-8",
    )
    return yol


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tarih", help="YYYY-AA-GG (varsayilan: bugun)")
    p.add_argument("--post", action="store_true", help="kuyruga post .md yaz")
    p.add_argument("--liste", action="store_true", help="yaklasan bayramlari listele")
    p.add_argument("--saat", default="09:00")
    a = p.parse_args()

    bugun = dt.datetime.now(TZ).date()

    if a.liste:
        print(f"Bugun: {bugun}\n")
        for t, b in yaklasanlar(bugun):
            kalan = (t - bugun).days
            isaret = "  <-- BUGUN" if kalan == 0 else ""
            uyari = "  [TARIH DOGRULANMALI]" if b.get("dogrulanmali") else ""
            print(f"{t}  {kalan:>4} gun  {b['tur']:<8} {b['ad']}{isaret}{uyari}")
        return

    tarih = dt.date.fromisoformat(a.tarih) if a.tarih else bugun
    bayram = bul(tarih)
    if not bayram:
        print(f"{tarih} icin bayram tanimi yok.")
        return

    if bayram.get("dogrulanmali"):
        print(f"UYARI: '{bayram['ad']}' tarihi dogrulanmali (dini bayram, Diyanet takvimi).")

    p_post, p_hikaye = uret(bayram, tarih)
    print(f"{bayram['ad']}  ({bayram['tur']})")
    print(f"  post   : {p_post}")
    print(f"  hikaye : {p_hikaye}")
    if a.post:
        print(f"  kuyruk : {post_yaz(bayram, tarih, p_post, a.saat)}")


if __name__ == "__main__":
    main()
