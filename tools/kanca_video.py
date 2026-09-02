# -*- coding: utf-8 -*-
"""Organik akış için 3D ürün videoları — ilk saniyede kanca.

Kullanıcı 28.08: *"instagram ve facebookta yeterince carousel'li video
paylaştık, şu 3D videolardan yapalım artık kancalı, onları öne al."*

Reklam videolarından farkı: burada **fiyat hiç yazmıyor** (kullanıcı 28.08).
Organik akışta satan şey ilk saniye — soru ya da iddia. Rakam akışta merakı
bitiriyor; fiyat ürün sayfasında, karar anında görülüyor. Aynı kural hikâye
arşivinde de geçerli.

Yerleşim TikTok/Reels arayüzüne göre:

    y 200-420   → kanca (koyu panel, beyaz yazı)
    y 460-1410  → ürün, 3D dönüş klibi (üstüne HİÇBİR yazı gelmiyor)
    y 1440-1530 → ürün adı + tek satır özellik

Zemini klibin kendi bulanık kopyası dolduruyor; yazılar hep o bulanık alanda
kalıyor, ürünün üstüne binmiyor. Sağ kenarda TikTok'un simge sütunu var, ürün
ortalanıp 900 piksele sığdırılıyor.

**Kling filigranı** için klibin alt %7'si kırpılıyor.
**Ses yok:** Pinterest bu müziklerden telif verdi, TikTok da telif denetimi
yapıyor ve takılan video sessize alınıyor — sessize alınan video dağıtım da
alamıyor. Ses TikTok'un kendi kütüphanesinden eklenmeli.

    python tools/kanca_video.py

"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw  # noqa: E402

from src.carousel_gorsel import _bold, _mono, _normal, _sigdir  # noqa: E402

KOK = pathlib.Path(__file__).resolve().parents[1]
KLIPLER = pathlib.Path.home() / "Desktop" / "kling-videolar"
CIKTI = KOK / "posts" / "media"
LOGO = KOK / "posts" / "media" / "marka" / "logo.png"

W, H = 1080, 1920
URUN_KUTU = (90, 460, 990, 1410)     # 900x950 — TikTok'un sag simge sutunu disinda
KLIP_SN = 3.0

LACIVERT = (11, 20, 32)
BEYAZ = (255, 255, 255)
ALTIN = (198, 158, 92)

VIDEOLAR = [
    {
        "dosya": "kanca3d-arduino-46.mp4",
        "klipler": ["kling_20260823_arduino46-turntable_4667.mp4",
                    "kling_20260823_arduino46-spotlight_4846.mp4"],
        "kanca": "Arduino'ya nereden başlanır?",
        "urun": "Arduino Başlangıç Seti · 46 parça",
        "alt": "Türkçe kaynak ve devre örnekleriyle",
    },
    {
        "dosya": "kanca3d-arduino-56.mp4",
        "klipler": ["kling_20260823_arduino56-dolly_4652.mp4"],
        "kanca": "Sensörlü projeye geçme vakti",
        "urun": "Arduino Proje Geliştirme Seti · 56 parça",
        "alt": "Modüller, sürücüler ve sensörler dahil",
    },
    {
        "dosya": "kanca3d-arduino-88.mp4",
        "klipler": ["kling_20260823_arduino88-dolly_4781.mp4"],
        "kanca": "Bir yıl yetecek tek kutu",
        "urun": "Arduino İleri Seviye Seti · 88 parça",
        "alt": "Dönem boyunca tek kutu yeter",
    },
    {
        "dosya": "kanca3d-sensor-seti.mp4",
        "klipler": ["kling_20260823_sensor-seti-orbit_4657.mp4",
                    "kling_20260823_sensor-seti-dolly_4867.mp4"],
        "kanca": "10 modül, 10 ayrı proje",
        "urun": "Akıllı Proje ve Sensör Modülleri Seti",
        "alt": "Röle · LCD · RFID · servo · mesafe",
    },
    {
        "dosya": "kanca3d-multimetre.mp4",
        "klipler": ["kling_20260823_multimetre-3d_4700.mp4",
                    "kling_20260823_multimetre-orbit_4885b.mp4"],
        "kanca": "Priz neden çalışmıyor?",
        "urun": "DT830D Buzzerlı Dijital Multimetre",
        "alt": "Buzzerlı — kopuk devreyi duyuyorsun",
    },
    {
        "dosya": "kanca3d-temrin-defteri.mp4",
        "klipler": ["kling_20260823_temrin-spotlight_4868b.mp4",
                    "kling_20260823_temrin-defteri-v2_4758.mp4"],
        "kanca": "Okul listesindeki o defter",
        "urun": "Atölye Temrin Defteri · 96 sayfa",
        "alt": "Tekli ve sınıf paketi stokta",
    },
]


def _ffmpeg() -> str:
    yol = shutil.which("ffmpeg")
    if not yol:
        raise SystemExit("HATA: ffmpeg bulunamadi. Kurulu mu, PATH'te mi?")
    return yol


def katman_uret(video: dict, hedef: pathlib.Path) -> pathlib.Path:
    """Kanca ve ürün şeridini saydam katman olarak çizer.

    Zemine değil videonun üstüne biniyor: kareyi baştan sona klip kaplıyor.
    """
    kat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(kat)

    # --- Kanca: ilk saniyede okunacak tek şey ---
    fk, satirlar, boyut = _sigdir(d, video["kanca"], W - 200, [([72, 64], 2), ([56], 3)])
    yuk = len(satirlar) * int(boyut * 1.2)
    y0 = 200
    d.rounded_rectangle([70, y0 - 30, W - 70, y0 + yuk + 24], radius=26,
                        fill=LACIVERT + (225,))
    y = y0
    for s in satirlar:
        d.text(((W - d.textlength(s, font=fk)) / 2, y), s, font=fk, fill=BEYAZ)
        y += int(boyut * 1.2)

    # --- Ürün adı + tek satır özellik ---
    # Organik paylaşımda FİYAT YAZILMIYOR (kullanıcı 28.08). Fiyat, ürün
    # sayfasında karar anında görülüyor; akışta rakam görmek merakı bitiriyor
    # ve tıklamayı düşürüyor. Aynı kural hikâye arşivinde de geçerli.
    fu = _bold(44)
    while d.textlength(video["urun"], font=fu) > W - 220 and fu.size > 30:
        fu = _bold(fu.size - 2)
    fa = _normal(34)
    while d.textlength(video["alt"], font=fa) > W - 220 and fa.size > 24:
        fa = _normal(fa.size - 2)
    alt = 1440
    d.rounded_rectangle([70, alt - 24, W - 70, alt + 108], radius=26,
                        fill=LACIVERT + (225,))
    d.text(((W - d.textlength(video["urun"], font=fu)) / 2, alt),
           video["urun"], font=fu, fill=BEYAZ)
    d.text(((W - d.textlength(video["alt"], font=fa)) / 2, alt + 56),
           video["alt"], font=fa, fill=ALTIN)

    # --- Marka: sol altta küçük, TikTok'un kendi yazıları sağda ---
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((104, 104), Image.LANCZOS)
    kat.alpha_composite(logo, (54, 1600))
    fm = _mono(24)
    d.text((172, 1636), "atolyeelektronik.com", font=fm, fill=BEYAZ)

    kat.save(hedef)
    return hedef


def uret(ffmpeg: str, video: dict) -> pathlib.Path:
    ux0, uy0, ux1, uy1 = URUN_KUTU
    uw, uh = ux1 - ux0, uy1 - uy0
    katman = katman_uret(video, CIKTI / "_kanca.png")

    girdiler: list[str] = []
    for ad in video["klipler"]:
        yol = KLIPLER / ad
        if not yol.exists():
            raise SystemExit(f"HATA: klip yok -> {yol}")
        girdiler += ["-i", str(yol)]
    girdiler += ["-loop", "1", "-i", str(katman)]

    parcalar = []
    for i in range(len(video["klipler"])):
        # Alt %7: Kling filigranı orada.
        parcalar.append(
            f"[{i}:v]trim=0:{KLIP_SN},setpts=PTS-STARTPTS,"
            f"crop=iw:trunc(ih*0.93/2)*2:0:0,fps=30,split=2[b{i}][f{i}];"
            # Zemin: karenin tamamını dolduran bulanık kopya
            f"[b{i}]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},gblur=sigma=34[bg{i}];"
            # Ürün: kutuya SIĞDIRILIYOR, kırpılmıyor
            f"[f{i}]scale={uw}:{uh}:force_original_aspect_ratio=decrease[fg{i}];"
            f"[bg{i}][fg{i}]overlay={ux0}+({uw}-overlay_w)/2:{uy0}+({uh}-overlay_h)/2,"
            f"setsar=1[c{i}]"
        )
    zincir = "".join(f"[c{i}]" for i in range(len(video["klipler"])))
    parcalar.append(f"{zincir}concat=n={len(video['klipler'])}:v=1[kl]")
    parcalar.append(f"[kl][{len(video['klipler'])}:v]overlay=0:0:shortest=1[v]")

    hedef = CIKTI / video["dosya"]
    subprocess.run(
        [ffmpeg, "-v", "error", "-y", *girdiler,
         "-filter_complex", ";".join(parcalar),
         "-map", "[v]", "-an",
         "-t", str(KLIP_SN * len(video["klipler"])),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(hedef)],
        check=True)
    katman.unlink()
    return hedef


def main() -> int:
    ffmpeg = _ffmpeg()
    for v in VIDEOLAR:
        yol = uret(ffmpeg, v)
        sn = KLIP_SN * len(v["klipler"])
        print(f"  uretildi: {yol.name}  ({yol.stat().st_size // 1024} KB, {sn:.0f} sn)")
    print(f"\n{len(VIDEOLAR)} kancali 3D video -> {CIKTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
