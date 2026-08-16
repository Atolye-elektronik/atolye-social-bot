"""Urun fotograflarini Instagram icin 4:5 kareye yerlestirir.

Neden gerekli:
  Instagram akista en fazla 4:5 (1080x1350) dikey gorsel kabul ediyor;
  profil izgarasi ise 3:4 gosteriyor. Magazanin urun fotograflari 3:2
  yatay (1800x1200) oldugu icin dogrudan paylasilinca Instagram kenarlari
  kirpiyor ve urun yarim gorunuyor.

  Bu modul her fotografi 1080x1350 beyaz zemine TAM SIGDIRIR (kirpmaz),
  altina urun adini ve marka satirini koyar. Onemli her sey ortadaki
  guvenli alanda kalir, boylece profil izgarasinda da kirpilmaz.

Kullanimi:
    python -m src.gorsel https://.../urun.png "Kontrol Kalemi" posts/media/x.jpg
"""

from __future__ import annotations

import io
import os
import pathlib
import sys

import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350                 # Instagram akis icin en uzun dikey oran (4:5)
KENAR = 48                        # profil izgarasi (3:4) yan kirpmasi icin pay
LACIVERT = (13, 27, 42)
ALTIN = (183, 142, 84)
GRI = (108, 122, 137)

FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    # Windows'ta DejaVu yok; gorseli yerelde uretebilmek icin sistem yazi
    # tiplerine dusuyoruz. carousel_gorsel.py ile ayni davranis.
    r"C:\Windows\Fonts",
]

# DejaVu bulunamazsa hangi sistem yazi tipi yerine gecsin.
FONT_KARSILIK = {
    "DejaVuSans-Bold.ttf": ("arialbd.ttf", "segoeuib.ttf", "calibrib.ttf"),
    "DejaVuSans.ttf": ("arial.ttf", "segoeui.ttf", "calibri.ttf"),
}


def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    ad = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    adaylar = (ad,) + FONT_KARSILIK.get(ad, ())
    for d in FONT_DIRS:
        for aday in adaylar:
            yol = os.path.join(d, aday)
            if os.path.exists(yol):
                return ImageFont.truetype(yol, size)
    # Eskiden burada ImageFont.load_default() vardi. O font olceklenmiyor
    # (istenen punto yok sayiliyor) ve Turkce harfleri kutu ciziyor; sonucta
    # okunmaz bir gorsel sessizce paylasiliyordu. Artik gurultulu basariszlik:
    # bozuk gorsel yayinlamaktansa is dursun.
    raise RuntimeError(
        f"Yazi tipi bulunamadi ({ad}). Aranan yerler: {', '.join(FONT_DIRS)}. "
        "CI'da 'fonts-dejavu-core' paketinin kurulu oldugundan emin ol."
    )


def _sar(d: ImageDraw.ImageDraw, metin: str, f, maxw: int, maxsatir: int = 2) -> list[str]:
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
        satirlar[-1] = satirlar[-1][:-3] + "..."
    return satirlar


def _indir(url: str) -> Image.Image:
    r = requests.get(url, headers={"User-Agent": "atolye-social-bot"}, timeout=90)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content))


def _duz_zemin(im: Image.Image) -> Image.Image:
    """Saydam PNG'leri beyaz zemine oturtur."""
    im = im.convert("RGBA")
    zemin = Image.new("RGBA", im.size, (255, 255, 255, 255))
    zemin.alpha_composite(im)
    return zemin.convert("RGB")


def kare_yap(kaynak, baslik: str, cikti: str | pathlib.Path,
             alt_yazi: str = "atolyeelektronik.com") -> pathlib.Path:
    """kaynak: URL ya da yerel dosya yolu."""
    if isinstance(kaynak, str) and kaynak.startswith(("http://", "https://")):
        urun = _indir(kaynak)
    else:
        urun = Image.open(kaynak)
    urun = _duz_zemin(urun)

    tuval = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(tuval)

    # --- urun alani: 1080x1350'nin ust kismi, TAM SIGAR (kirpma yok) ---
    alan_w, alan_h = W - 2 * (KENAR + 30), 940
    oran = min(alan_w / urun.size[0], alan_h / urun.size[1])
    yeni = (max(1, int(urun.size[0] * oran)), max(1, int(urun.size[1] * oran)))
    urun = urun.resize(yeni, Image.LANCZOS)
    tuval.paste(urun, ((W - yeni[0]) // 2, 70 + (alan_h - yeni[1]) // 2))

    # --- alt bilgi seridi ---
    d.line([(KENAR + 40, 1075), (W - KENAR - 40, 1075)], fill=(226, 231, 237), width=3)

    fb = _font(True, 54)
    satirlar = _sar(d, baslik.strip(), fb, W - 2 * (KENAR + 40), maxsatir=2)
    y = 1130 if len(satirlar) > 1 else 1160
    for s in satirlar:
        d.text(((W - d.textlength(s, font=fb)) / 2, y), s, font=fb, fill=LACIVERT)
        y += 66

    fa = _font(False, 38)
    y = max(y + 12, 1258)
    d.text(((W - d.textlength(alt_yazi, font=fa)) / 2, y), alt_yazi, font=fa, fill=GRI)

    # --- ince marka cercevesi (guvenli alanin icinde) ---
    d.rounded_rectangle([KENAR, 30, W - KENAR, H - 30], radius=28,
                        outline=(233, 237, 242), width=3)
    d.line([(W // 2 - 60, 58), (W // 2 + 60, 58)], fill=ALTIN, width=5)

    cikti = pathlib.Path(cikti)
    cikti.parent.mkdir(parents=True, exist_ok=True)
    tuval.save(cikti, "JPEG", quality=92, optimize=True)
    return cikti


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit("kullanim: python -m src.gorsel <url|dosya> <baslik> <cikti.jpg>")
    kare_yap(sys.argv[1], sys.argv[2], sys.argv[3])
    print(f"olusturuldu: {sys.argv[3]}")


if __name__ == "__main__":
    main()
