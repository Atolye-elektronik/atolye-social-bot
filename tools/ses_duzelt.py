# -*- coding: utf-8 -*-
"""Videoların ses seviyesini ölçer ve alçak kalanları standarda oturtur.

Neden var: 27.08.2026'da "YouTube'da sessiz videolar" şikâyeti araştırıldı.
Videolar aslında sessiz değildi — ses izi vardı, telif bildirimi de yoktu —
ama elle kurgulanan videolarda seviye **-25 ile -36 dB** arasına düşmüştü.
Telefon hoparlöründe bu pratikte duyulmuyor. Karuselden üretilenler -14…-16 dB
ile normaldi; fark buradan geliyordu. `tanitim.mp4` ise -91 dB, yani ses izi
tamamen boştu.

Hedef -14 LUFS: YouTube, TikTok ve Instagram'ın kendi normalizasyon hedefi.
Bu seviyede gönderilen ses platformda olduğu gibi kalır.

Görüntüye dokunulmaz (`-c:v copy`), yalnız ses yeniden kodlanır.

    python tools/ses_duzelt.py                 # sadece ölç ve raporla
    python tools/ses_duzelt.py --uygula        # alçak olanları düzelt
    python tools/ses_duzelt.py --uygula --esik -20
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys

MEDYA = pathlib.Path(__file__).resolve().parents[1] / "posts" / "media"
HEDEF_LUFS = -14.0
# Bu seviyenin altındaki videolar düzeltilir. -20 dB mean_volume, telefonda
# duyulur olmanın alt sınırı sayılabilir.
VARSAYILAN_ESIK = -20.0
# Bunun altı "ses izi var ama içi boş" demek; normalize etmek işe yaramaz,
# müzik yeniden eklenmeli.
BOS_SES = -80.0

MEAN_RE = re.compile(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB")


def _ffmpeg() -> str:
    yol = shutil.which("ffmpeg")
    if yol is None:
        raise SystemExit("ffmpeg bulunamadi.")
    return yol


def ses_izi_var(video: pathlib.Path) -> bool:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True,
    )
    return bool(r.stdout.strip())


def seviye_olc(video: pathlib.Path) -> float | None:
    r = subprocess.run(
        [_ffmpeg(), "-i", str(video), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    m = MEAN_RE.search(r.stderr)
    return float(m.group(1)) if m else None


def duzelt(video: pathlib.Path) -> None:
    """Sesi -14 LUFS'a oturtur. Goruntu kopyalanir, bozulmaz."""
    gecici = video.with_suffix(".sesduzelt.mp4")
    subprocess.run(
        [_ffmpeg(), "-y", "-loglevel", "error", "-i", str(video),
         "-af", f"loudnorm=I={HEDEF_LUFS}:TP=-1.5:LRA=11",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", str(gecici)],
        check=True,
    )
    gecici.replace(video)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true", help="duzeltmeyi gercekten yap")
    ap.add_argument("--esik", type=float, default=VARSAYILAN_ESIK,
                    help=f"bu dB'nin altindakiler duzeltilir (varsayilan {VARSAYILAN_ESIK})")
    a = ap.parse_args()

    dusuk, sessiz, tamam = [], [], 0
    for video in sorted(MEDYA.glob("*.mp4")):
        if not ses_izi_var(video):
            sessiz.append((video, None))
            continue
        seviye = seviye_olc(video)
        if seviye is None:
            continue
        if seviye <= BOS_SES:
            sessiz.append((video, seviye))
        elif seviye < a.esik:
            dusuk.append((video, seviye))
        else:
            tamam += 1

    print(f"{tamam} video zaten yeterli seviyede.\n")

    if sessiz:
        print(f"SESSIZ ({len(sessiz)}) — normalize edilemez, muzik yeniden eklenmeli:")
        for v, s in sessiz:
            print(f"   {v.name}  ({'ses izi yok' if s is None else f'{s} dB'})")
        print()

    if not dusuk:
        print("Seviyesi dusuk video yok.")
        return 0

    print(f"SEVIYESI DUSUK ({len(dusuk)}) — hedef {HEDEF_LUFS} LUFS:")
    for v, s in dusuk:
        print(f"   {s:6.1f} dB  {v.name}")

    if not a.uygula:
        print("\n--- KURU CALISMA --- gercekten duzeltmek icin: --uygula")
        return 0

    print()
    for v, eski in dusuk:
        duzelt(v)
        yeni = seviye_olc(v)
        print(f"   {eski:6.1f} -> {yeni:6.1f} dB   {v.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
