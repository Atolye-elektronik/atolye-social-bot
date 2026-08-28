# -*- coding: utf-8 -*-
"""Mevcut kurgu videolarını ücretli reklama uygun hale getirir.

Organik paylaşımda sorun olmayan üç şey ücretli reklamda sorun:

  1. **Kling filigranı.** Videoların sağ altında "KlingAI 3.0" duruyor. Organik
     akışta gözden kaçıyor ama para verdiğimiz bir reklamda başka bir markanın
     adı görünüyor; Meta üçüncü taraf markasını da inceliyor. Bulanıklaştırmak
     yerine kendi köşe etiketimizi koyuyoruz — silme değil, kapatma; sonuç
     lekeli değil kasıtlı görünüyor.

  2. **ATOLYE10 kuponu.** Videoların kapanışında "ATOLYE10 ile %10" yazıyor.
     Fiyatlara ATOLYE10'u nötrlemek için %11,2 zam yapıldı; kuponu reklamda
     duyurmak indirimi her alıcıya dağıtmak demek. O satır "aynı gün kargo"
     ile değiştiriliyor.

  3. **Müzik telifi.** Pinterest bu videolardan ses telifi verdi. Reklamda
     telifli müzik reddedilme ya da sessize alınma sebebi; 1 Eylül lansmanının
     hemen öncesinde reklam hesabını riske atmaya değmez. Reklam kopyaları
     sessiz üretiliyor — Meta akışı zaten büyük ölçüde sessiz izleniyor,
     anlatım ekrandaki yazılarla yürüyor.

    python tools/reklam_video.py
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw  # noqa: E402

from src.carousel_gorsel import _bold, _mono  # noqa: E402

KOK = pathlib.Path(__file__).resolve().parents[1]
KAYNAK = KOK / "posts" / "media"
CIKTI = KAYNAK / "meta-reklam"

W, H = 1080, 1920

LACIVERT = (11, 20, 32)
TEAL = (13, 132, 124)
BEYAZ = (255, 255, 255)

# Kupon satırının yeri tüm kurgu videolarında aynı (ölçüldü 28.08). Şerit
# bilerek neredeyse tam genişlikte: bazı videolarda özgün kupon yazısı daha
# geniş ve dar bir kutu kenarlardan sızıyor.
KUPON_KUTU = (16, 1180, 1064, 1292)
KUPON_METIN = "Aynı gün kargo · atolyeelektronik.com"

# Kling filigranı sağ altta, yine sabit yerde.
KOSE_KUTU = (798, 1588, 1062, 1662)
KOSE_METIN = "ATÖLYE ELEKTRONİK"

VIDEOLAR = [
    ("kurgu-is-dosyasi.mp4", "reklam-staj-defteri.mp4"),
    ("kurgu-temrin-defteri.mp4", "reklam-temrin-defteri.mp4"),
    ("kurgu-takim-cantasi.mp4", "reklam-takim-cantasi.mp4"),
    ("kurgu2-endustriyel.mp4", "reklam-endustriyel.mp4"),
    ("kurgu-arduino-seti.mp4", "reklam-arduino.mp4"),
]


def _ffmpeg() -> str:
    yol = shutil.which("ffmpeg")
    if not yol:
        raise SystemExit("HATA: ffmpeg bulunamadi. Kurulu mu, PATH'te mi?")
    return yol


def kapak_uret(hedef: pathlib.Path) -> pathlib.Path:
    """İki kapatma şeridini saydam bir PNG olarak çizer."""
    kat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(kat)

    # Kupon satırının üstüne aynı görsel dilde koyu şerit
    x0, y0, x1, y1 = KUPON_KUTU
    d.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=LACIVERT + (255,))  # tam opak: yari saydamda eski kupon yazisi altindan okunuyor
    f = _bold(38)
    while d.textlength(KUPON_METIN, font=f) > (x1 - x0) - 48 and f.size > 22:
        f = _bold(f.size - 2)
    d.text((x0 + ((x1 - x0) - d.textlength(KUPON_METIN, font=f)) / 2,
            y0 + ((y1 - y0) - f.size) / 2 - 4),
           KUPON_METIN, font=f, fill=BEYAZ)

    # Filigranın üstüne kendi köşe etiketimiz
    x0, y0, x1, y1 = KOSE_KUTU
    d.rounded_rectangle([x0, y0, x1, y1], radius=(y1 - y0) / 2, fill=TEAL + (255,))
    f = _mono(24)
    while d.textlength(KOSE_METIN, font=f) > (x1 - x0) - 36 and f.size > 14:
        f = _mono(f.size - 1)
    d.text((x0 + ((x1 - x0) - d.textlength(KOSE_METIN, font=f)) / 2,
            y0 + ((y1 - y0) - f.size) / 2 - 3),
           KOSE_METIN, font=f, fill=BEYAZ)

    kat.save(hedef)
    return hedef


def uret(ffmpeg: str, kapak: pathlib.Path, kaynak: str, cikti: str) -> pathlib.Path:
    girdi = KAYNAK / kaynak
    if not girdi.exists():
        raise SystemExit(f"HATA: kaynak video yok -> {girdi}")
    hedef = CIKTI / cikti
    komut = [
        ffmpeg, "-v", "error", "-y",
        "-i", str(girdi),
        "-i", str(kapak),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
        "-map", "[v]",
        "-an",                       # ses telifi: reklam kopyaları sessiz
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(hedef),
    ]
    subprocess.run(komut, check=True)
    return hedef


def main() -> int:
    ffmpeg = _ffmpeg()
    CIKTI.mkdir(parents=True, exist_ok=True)
    kapak = kapak_uret(CIKTI / "_kapak.png")
    for kaynak, cikti in VIDEOLAR:
        yol = uret(ffmpeg, kapak, kaynak, cikti)
        print(f"  uretildi: {yol.name}  ({yol.stat().st_size // 1024} KB)")
    kapak.unlink()
    print(f"\n{len(VIDEOLAR)} reklam videosu -> {CIKTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
