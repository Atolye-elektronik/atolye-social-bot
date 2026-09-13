# -*- coding: utf-8 -*-
"""Feed gorselini kirpilmadan hikayeye sigdirir.

Instagram hikayesi 9:16. Feed gorsellerimiz 1080x1350 (4:5) ve carousel
slaytlari 1080x1080; bunlari oldugu gibi hikaye olarak atinca Instagram
genisligi doldurup SAGDAN VE SOLDAN KIRPIYOR — basliklarin bas ve son
harfleri kesiliyordu (13.09.2026 kullanici bildirimi).

Cozum: 1080x1920 tuval, gorsel genisligi bozmadan ortalanir, ust/alt bantlar
gorselin KENDI zemin rengiyle doldurulur. Zemin duz koyu lacivert oldugu icin
ek bant gozukmez; hikaye tek parca gibi durur.

Video icin: 9:16 disindaki videolar ayni mantikla pillarbox/letterbox edilir.
"""
from __future__ import annotations

import pathlib
import subprocess

from PIL import Image

W, H = 1080, 1920
EK = "-hikaye"
VIDEO_UZANTI = (".mp4", ".mov", ".m4v")


def _zemin_rengi(img: Image.Image) -> tuple[int, int, int]:
    """Gorselin kose piksellerinin medyani — zemin rengi."""
    k = 6
    n = [img.getpixel(p) for p in ((k, k), (img.width - k, k), (k, img.height - k), (img.width - k, img.height - k))]
    return tuple(sorted(c[i] for c in n)[len(n) // 2] for i in range(3))


def hikaye_yolu(kaynak: str | pathlib.Path) -> pathlib.Path:
    p = pathlib.Path(kaynak)
    return p.with_name(p.stem + EK + p.suffix)


def gorsel_hikaye(kaynak: str | pathlib.Path, hedef: str | pathlib.Path | None = None) -> pathlib.Path:
    kaynak = pathlib.Path(kaynak)
    hedef = pathlib.Path(hedef) if hedef else hikaye_yolu(kaynak)
    img = Image.open(kaynak).convert("RGB")
    if img.width * H == img.height * W:          # zaten 9:16
        return kaynak
    olcek = min(W / img.width, H / img.height)
    yeni = img.resize((round(img.width * olcek), round(img.height * olcek)), Image.LANCZOS)
    tuval = Image.new("RGB", (W, H), _zemin_rengi(img))
    tuval.paste(yeni, ((W - yeni.width) // 2, (H - yeni.height) // 2))
    hedef.parent.mkdir(parents=True, exist_ok=True)
    tuval.save(hedef, quality=92, subsampling=0)
    return hedef


def video_hikaye(kaynak: str | pathlib.Path, hedef: str | pathlib.Path | None = None) -> pathlib.Path:
    kaynak = pathlib.Path(kaynak)
    hedef = pathlib.Path(hedef) if hedef else hikaye_yolu(kaynak)
    try:
        o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(kaynak)],
                           capture_output=True, text=True, timeout=60)
        g, y = (int(x) for x in o.stdout.strip().split("x")[:2])
        if g * H == y * W:
            return kaynak
    except Exception:
        return kaynak
    vf = ("scale=%d:%d:force_original_aspect_ratio=decrease,"
          "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=0x0B1420" % (W, H, W, H))
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(kaynak), "-vf", vf,
                        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-c:a", "copy", str(hedef)],
                       capture_output=True, text=True, timeout=900)
    return hedef if r.returncode == 0 and hedef.exists() else kaynak


def hikaye_surumu(kaynak: str | pathlib.Path, video: bool = False) -> pathlib.Path:
    """Varsa hazir hikaye surumunu, yoksa uretip dondurur; uretemezse kaynagi."""
    kaynak = pathlib.Path(kaynak)
    hazir = hikaye_yolu(kaynak)
    if hazir.exists():
        return hazir
    if not kaynak.exists():
        return kaynak
    try:
        if video or kaynak.suffix.lower() in VIDEO_UZANTI:
            return video_hikaye(kaynak)
        return gorsel_hikaye(kaynak)
    except Exception:
        return kaynak


def eksikleri_uret(kok: str | pathlib.Path = "posts/media") -> int:
    """Hikayeye giden gorsellerin 9:16 surumunu uretir.

    Hikaye yalniz postun ILK medyasini kullaniyor: ust dizindeki post gorselleri
    ve carousel kapaklari. Ic slaytlar (02-urun.jpg ...) hikayeye hic gitmiyor,
    onlara surum uretmiyoruz - bosuna 70 MB depo sismesin.
    """
    kok = pathlib.Path(kok)
    hedefler = [p for p in sorted(kok.glob("*")) if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    hedefler += sorted(kok.glob("carousel/*/01-kapak.jpg"))
    n = 0
    for p in hedefler:
        if EK in p.stem or hikaye_yolu(p).exists():
            continue
        try:
            if gorsel_hikaye(p) != p:
                n += 1
        except Exception as e:
            print("  ! %s: %s" % (p.name, str(e)[:80]))
    return n


if __name__ == "__main__":
    import sys
    kok = sys.argv[1] if len(sys.argv) > 1 else "posts/media"
    print("%d hikaye surumu uretildi" % eksikleri_uret(kok))
