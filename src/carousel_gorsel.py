"""Instagram/Facebook carousel'i icin marka stilinde slide uretir.

Stil, magazanin Instagram'daki mevcut carousel'inden alindi:
koyu lacivert zemin, turkuaz devre karti izleri, turuncu vurgular,
buyuk beyaz basliklar ve "atolyeelektronik.com" pill butonu.

Uc tip slide var:
  kapak(...)   — urun adiyla acilis slide'i
  urun(...)    — beyaz kart icinde urun fotografi + baslik + sayac
  kapanis(...) — siparis cagrisi (CTA) slide'i

Kullanimi:
    python -m src.carousel_gorsel  # ornek slide'lar uretir (onizleme)
"""

from __future__ import annotations

import io
import os
import pathlib
import random

import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350                     # Instagram 4:5

ZEMIN = (11, 20, 32)                  # koyu lacivert
ZEMIN_ACIK = (17, 30, 46)
TURKUAZ = (46, 224, 208)
TURKUAZ_SOLUK = (46, 224, 208, 90)
TURUNCU = (255, 122, 61)
BEYAZ = (240, 246, 250)
GRI = (138, 154, 170)
ALTIN = (183, 142, 84)

SITE = "atolyeelektronik.com"
MARKA = "ATÖLYE ELEKTRONİK"

FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    # Windows'ta DejaVu yok; slide'lari yerelde uretebilmek icin sistem
    # yazi tiplerine dusuyoruz. Bu olmadan PIL minik bir bitmap fontu
    # kullaniyor ve Turkce karakterler kutu olarak ciziliyor.
    r"C:\Windows\Fonts",
]

# DejaVu bulunamazsa hangi sistem yazi tipi yerine gecsin.
FONT_KARSILIK = {
    "DejaVuSans-Bold.ttf": ("arialbd.ttf", "segoeuib.ttf", "calibrib.ttf"),
    "DejaVuSans.ttf": ("arial.ttf", "segoeui.ttf", "calibri.ttf"),
    "DejaVuSansMono-Bold.ttf": ("consolab.ttf", "cour.ttf", "arialbd.ttf"),
}


def _font(ad: str, size: int) -> ImageFont.FreeTypeFont:
    adaylar = (ad,) + FONT_KARSILIK.get(ad, ())
    for d in FONT_DIRS:
        for aday in adaylar:
            yol = os.path.join(d, aday)
            if os.path.exists(yol):
                return ImageFont.truetype(yol, size)
    # gorsel.py ile ayni gerekce: load_default() olceklenmiyor ve Turkce
    # harfleri kutu ciziyor. Bozuk slide uretmektense is dursun.
    raise RuntimeError(
        f"Yazi tipi bulunamadi ({ad}). Aranan yerler: {', '.join(FONT_DIRS)}. "
        "CI'da 'fonts-dejavu-core' paketinin kurulu oldugundan emin ol."
    )


def _bold(size: int) -> ImageFont.FreeTypeFont:
    return _font("DejaVuSans-Bold.ttf", size)


def _normal(size: int) -> ImageFont.FreeTypeFont:
    return _font("DejaVuSans.ttf", size)


def _mono(size: int) -> ImageFont.FreeTypeFont:
    f = _font("DejaVuSansMono-Bold.ttf", size)
    return f


def _aralikli(d: ImageDraw.ImageDraw, xy, metin: str, f, fill, aralik: int = 6) -> float:
    """Harf aralikli (letter-spaced) metin cizer, toplam genisligi dondurur."""
    x, y = xy
    for harf in metin:
        d.text((x, y), harf, font=f, fill=fill)
        x += d.textlength(harf, font=f) + aralik
    return x - xy[0] - aralik


def _aralikli_genislik(d: ImageDraw.ImageDraw, metin: str, f, aralik: int = 6) -> float:
    toplam = sum(d.textlength(h, font=f) for h in metin)
    return toplam + aralik * (len(metin) - 1)


def _tam(satirlar: list[str], metin: str) -> bool:
    return " ".join(satirlar) == " ".join(metin.split())


def _sigdir(d: ImageDraw.ImageDraw, metin: str, maxw: int,
            kademeler: list[tuple[list[int], int]], bold: bool = True):
    """Metni kirpmadan sigdiran en buyuk fontu secer: (font, satirlar, boyut).

    kademeler: (font boyutlari, izin verilen satir sayisi) ciftleri.
    Once buyuk font/az satir denenir; hicbiri yetmezse en kucugu kirparak kullanir.
    """
    yapici = _bold if bold else _normal
    for boyutlar, maxsatir in kademeler:
        for boyut in boyutlar:
            f = yapici(boyut)
            satirlar = _sar(d, metin, f, maxw, maxsatir=maxsatir)
            if _tam(satirlar, metin):
                return f, satirlar, boyut
    boyutlar, maxsatir = kademeler[-1]
    f = yapici(boyutlar[-1])
    return f, _sar(d, metin, f, maxw, maxsatir=maxsatir), boyutlar[-1]


def _sar(d: ImageDraw.ImageDraw, metin: str, f, maxw: int, maxsatir: int = 3) -> list[str]:
    kelimeler, satirlar, cur = metin.split(), [], ""
    for k in kelimeler:
        deneme = (cur + " " + k).strip()
        if d.textlength(deneme, font=f) <= maxw:
            cur = deneme
        else:
            if cur:
                satirlar.append(cur)
            cur = k
        if len(satirlar) == maxsatir:
            break
    if cur and len(satirlar) < maxsatir:
        satirlar.append(cur)
    if len(satirlar) == maxsatir and d.textlength(satirlar[-1], font=f) > maxw - 40:
        satirlar[-1] = satirlar[-1].rstrip(".") [:-3] + "..."
    return satirlar


def _devre_izi(d: ImageDraw.ImageDraw, rnd: random.Random, bolge: tuple[int, int, int, int],
               adet: int = 10) -> None:
    """Devre karti izleri: 45 derece kirilan cizgiler, uclarinda pad noktalari."""
    x0, y0, x1, y1 = bolge
    for _ in range(adet):
        renk = TURUNCU if rnd.random() < 0.2 else TURKUAZ
        katsayi = rnd.uniform(0.35, 0.8)
        ton = tuple(int(c * katsayi) for c in renk)
        x = rnd.randint(x0, x1)
        y = rnd.randint(y0, y1)
        yon = rnd.choice([(1, 0), (0, 1), (-1, 0), (0, -1)])
        d.ellipse([x - 5, y - 5, x + 5, y + 5], outline=ton, width=2)
        for _ in range(rnd.randint(2, 4)):
            adim = rnd.randint(40, 130)
            nx, ny = x + yon[0] * adim, y + yon[1] * adim
            nx = max(x0, min(x1, nx))
            ny = max(y0, min(y1, ny))
            d.line([(x, y), (nx, ny)], fill=ton, width=3)
            x, y = nx, ny
            # 45 derece veya dik kirilma
            yon = rnd.choice([(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)])
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=ton)


def _zemin(seed: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    tuval = Image.new("RGB", (W, H), ZEMIN)
    d = ImageDraw.Draw(tuval)
    rnd = random.Random(seed)
    # kose dekorlari — ortadaki icerik alanini bos birakir
    _devre_izi(d, rnd, (0, 0, W, 190), adet=8)
    _devre_izi(d, rnd, (0, H - 190, W, H), adet=8)
    _devre_izi(d, rnd, (0, 200, 130, H - 200), adet=5)
    _devre_izi(d, rnd, (W - 130, 200, W, H - 200), adet=5)
    return tuval, d


def _marka_baslik(d: ImageDraw.ImageDraw, y: int = 96) -> None:
    f = _mono(30)
    gen = _aralikli_genislik(d, MARKA, f, aralik=8)
    _aralikli(d, ((W - gen) / 2, y), MARKA, f, TURKUAZ, aralik=8)
    d.line([(W / 2 - 60, y - 26), (W / 2 + 60, y - 26)], fill=ALTIN, width=4)


def _pill(d: ImageDraw.ImageDraw, metin: str, cy: int, renk=TURUNCU,
          yazi=BEYAZ, f=None) -> None:
    f = f or _bold(38)
    gen = d.textlength(metin, font=f)
    ph, pw = 84, gen + 120
    x0, y0 = (W - pw) / 2, cy - ph / 2
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph / 2, fill=renk)
    d.text(((W - gen) / 2, cy - 26), metin, font=f, fill=yazi)


def _indir(url: str) -> Image.Image:
    r = requests.get(url, headers={"User-Agent": "atolye-social-bot"}, timeout=90)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content))


def _ac(kaynak) -> Image.Image:
    if isinstance(kaynak, str) and kaynak.startswith(("http://", "https://")):
        im = _indir(kaynak)
    else:
        im = Image.open(kaynak)
    im = im.convert("RGBA")
    zemin = Image.new("RGBA", im.size, (255, 255, 255, 255))
    zemin.alpha_composite(im)
    return zemin.convert("RGB")


def _kaydet(tuval: Image.Image, cikti) -> pathlib.Path:
    cikti = pathlib.Path(cikti)
    cikti.parent.mkdir(parents=True, exist_ok=True)
    tuval.save(cikti, "JPEG", quality=90, optimize=True)
    return cikti


def kapak(baslik: str, cikti, alt_baslik: str = "ÜRÜN TANITIMI") -> pathlib.Path:
    """Acilis slide'i: marka + buyuk urun adi + site pill'i."""
    tuval, d = _zemin(f"kapak:{baslik}")
    _marka_baslik(d)

    fk = _mono(34)
    gen = _aralikli_genislik(d, alt_baslik, fk, aralik=10)
    _aralikli(d, ((W - gen) / 2, 400), alt_baslik, fk, TURUNCU, aralik=10)

    fb, satirlar, boyut = _sigdir(
        d, baslik, W - 240, [([84, 72, 62], 3), ([56, 50, 44], 4), ([40, 36], 5)]
    )
    satir_yuksekligi = int(boyut * 1.24)
    y = 660 - len(satirlar) * satir_yuksekligi // 2
    for s in satirlar:
        d.text(((W - d.textlength(s, font=fb)) / 2, y), s, font=fb, fill=BEYAZ)
        y += satir_yuksekligi

    d.line([(W / 2 - 120, y + 40), (W / 2 + 120, y + 40)], fill=TURKUAZ, width=4)

    fo = _normal(36)
    # "kaydırın" demiyoruz: bu slaytlar Facebook'a da gidiyor ve orada gönderi
    # kaydırmalı carousel değil, çoklu fotoğraf albümü olarak çıkıyor.
    ok = "Detaylar fotoğraflarda"
    d.text(((W - d.textlength(ok, font=fo)) / 2, y + 90), ok, font=fo, fill=GRI)
    d.text((W / 2 + d.textlength(ok, font=fo) / 2 + 18, y + 88), "»", font=_bold(40), fill=TURKUAZ)

    _pill(d, SITE, 1190)
    return _kaydet(tuval, cikti)


def urun(kaynak, baslik: str, sira: int, toplam: int, cikti) -> pathlib.Path:
    """Urun fotografi slide'i: beyaz kart + baslik + sayfa sayaci."""
    tuval, d = _zemin(f"urun:{baslik}:{sira}")
    _marka_baslik(d, y=78)

    # beyaz kart
    kx0, ky0, kx1, ky1 = 80, 180, W - 80, 1020
    d.rounded_rectangle([kx0, ky0, kx1, ky1], radius=36, fill=(255, 255, 255))

    foto = _ac(kaynak)
    alan_w, alan_h = (kx1 - kx0) - 80, (ky1 - ky0) - 80
    oran = min(alan_w / foto.size[0], alan_h / foto.size[1])
    yeni = (max(1, int(foto.size[0] * oran)), max(1, int(foto.size[1] * oran)))
    foto = foto.resize(yeni, Image.LANCZOS)
    tuval.paste(foto, (kx0 + 40 + (alan_w - yeni[0]) // 2, ky0 + 40 + (alan_h - yeni[1]) // 2))

    # sayac rozetleri
    d.rounded_rectangle([W - 220, ky0 + 24, W - 116, ky0 + 78], radius=27, fill=ZEMIN)
    fs = _bold(34)
    sayac = f"{sira}/{toplam}"
    d.text((W - 168 - d.textlength(sayac, font=fs) / 2, ky0 + 32), sayac, font=fs, fill=TURKUAZ)

    fb, satirlar, boyut = _sigdir(
        d, baslik, W - 200, [([52, 46, 40], 2), ([38, 34, 30], 3)]
    )
    y = 1080 if len(satirlar) < 3 else 1056
    for s in satirlar:
        d.text(((W - d.textlength(s, font=fb)) / 2, y), s, font=fb, fill=BEYAZ)
        y += int(boyut * 1.24)

    fa = _normal(34)
    d.text(((W - d.textlength(SITE, font=fa)) / 2, max(y + 18, 1252)), SITE, font=fa, fill=GRI)
    return _kaydet(tuval, cikti)


def metin(etiket: str, baslik: str, satirlar: list[str], cikti,
          son: bool = False) -> pathlib.Path:
    """Senaryo (hikaye) slide'i: kisa etiket + buyuk baslik + aciklama satirlari.

    'son' False ise altta kaydirma ipucu gosterilir.
    """
    tuval, d = _zemin(f"metin:{etiket}:{baslik}")
    _marka_baslik(d)

    fk = _mono(34)
    gen = _aralikli_genislik(d, etiket, fk, aralik=10)
    _aralikli(d, ((W - gen) / 2, 360), etiket, fk, TURUNCU, aralik=10)

    fb, b_satirlar, boyut = _sigdir(
        d, baslik, W - 200, [([72, 62, 54], 3), ([48, 42], 4)]
    )
    y = 470
    for s in b_satirlar:
        d.text(((W - d.textlength(s, font=fb)) / 2, y), s, font=fb, fill=BEYAZ)
        y += int(boyut * 1.28)

    d.line([(W / 2 - 120, y + 30), (W / 2 + 120, y + 30)], fill=TURKUAZ, width=4)
    y += 80

    fo = _normal(40)
    for satir in satirlar:
        for s in _sar(d, satir, fo, W - 260, maxsatir=3):
            d.text(((W - d.textlength(s, font=fo)) / 2, y), s, font=fo, fill=GRI)
            y += 56
        y += 18

    if son:
        _pill(d, SITE, 1190)
    else:
        fo2 = _normal(36)
        ok = "devamı var"
        d.text(((W - d.textlength(ok, font=fo2)) / 2, 1180), ok, font=fo2, fill=GRI)
        d.text((W / 2 + d.textlength(ok, font=fo2) / 2 + 18, 1178), "»", font=_bold(40), fill=TURKUAZ)
    return _kaydet(tuval, cikti)


def kapanis(cikti, baslik_satirlari: list[str] | None = None,
            alt_yazi: str = "Arduino setleri • Sensörler • El aletleri") -> pathlib.Path:
    """CTA slide'i: siparis cagrisi."""
    tuval, d = _zemin("kapanis")
    _marka_baslik(d)

    fk = _mono(34)
    ust = "SİPARİŞ İÇİN"
    gen = _aralikli_genislik(d, ust, fk, aralik=10)
    _aralikli(d, ((W - gen) / 2, 430), ust, fk, TURUNCU, aralik=10)

    fb = _bold(76)
    for i, s in enumerate(baslik_satirlari or ["Online mağazamızı", "ziyaret edin!"]):
        d.text(((W - d.textlength(s, font=fb)) / 2, 520 + i * 96), s, font=fb, fill=BEYAZ)

    d.line([(W / 2 - 120, 760), (W / 2 + 120, 760)], fill=TURKUAZ, width=4)

    fo = _normal(38)
    d.text(((W - d.textlength(alt_yazi, font=fo)) / 2, 800), alt_yazi, font=fo, fill=GRI)

    # --- ATOLYE10 kupon kutusu ---
    kw, kh = 640, 150
    kx0, ky0 = (W - kw) / 2, 880
    d.rounded_rectangle([kx0, ky0, kx0 + kw, ky0 + kh], radius=20,
                        fill=ZEMIN_ACIK, outline=TURKUAZ, width=3)
    fk2 = _mono(26)
    etiket = "İLK ALIŞVERİŞE ÖZEL %10 İNDİRİM"
    gen2 = _aralikli_genislik(d, etiket, fk2, aralik=4)
    _aralikli(d, ((W - gen2) / 2, ky0 + 22), etiket, fk2, TURUNCU, aralik=4)
    fkod = _bold(56)
    kod = "ATOLYE10"
    d.text(((W - d.textlength(kod, font=fkod)) / 2, ky0 + 66), kod, font=fkod, fill=BEYAZ)

    _pill(d, SITE, 1120)

    fw = _normal(34)
    wp = "Hızlı kargo • Güvenli ödeme"
    d.text(((W - d.textlength(wp, font=fw)) / 2, 1210), wp, font=fw, fill=TURKUAZ)
    return _kaydet(tuval, cikti)


def main() -> None:
    cikti = pathlib.Path("onizleme")
    kapak("Temel Elektronik Deney Seti", cikti / "01-kapak.jpg")
    kapanis(cikti / "03-kapanis.jpg")
    print(f"ornek slide'lar {cikti}/ klasorune uretildi")


if __name__ == "__main__":
    main()
