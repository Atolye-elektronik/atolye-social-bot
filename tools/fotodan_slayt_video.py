"""Tek fotoğraflı gönderileri (urun_tanitim / ipucu / magaza / hafta_sonu) kısa
dikey slayt videoya çevirir ve postu video olarak paylaşılacak hale getirir.

07.10.2026 kullanıcı: "Instagram'da videolar azaldı, sadece fotoğraf atılıyor" →
"Kısa slayt yap, video olarak paylaş". Her gün en az bir video çıksın diye
fotoğraf gönderileri de Reels olarak gidiyor.

Kareler: postun kendi görseli + Shopify ürün sayfasındaki 2-3 fotoğraf
(caption'daki /products/<handle> linkinden). Kanca karesi temaya göre seçilir.
Müzik content/muzik içinden (video_uretim.muzik_sec).

    python tools/fotodan_slayt_video.py --kuru            # neler değişecek
    python tools/fotodan_slayt_video.py --slug <post>     # tek post
    python tools/fotodan_slayt_video.py --tumu            # bugünden sonraki hepsi

Video üretilince front matter'da `media:` mp4 olur, eski görsel
`kapak_gorsel:` satırında saklanır (geri dönmek için).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.request

KOK = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from src import video_uretim  # noqa: E402

TEMALAR = ("urun_tanitim", "ipucu", "magaza", "hafta_sonu")
KANCA = {
    "urun_tanitim": "Atölyede bunu gördün mü?",
    "ipucu": "Bunu bilen öğrenci az",
    "magaza": "Bugün sipariş ver, bugün kargoda",
    "hafta_sonu": "Hafta sonu projesi arayan?",
}
STORE = "https://atolyeelektronik.com"
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def _urun_gorselleri(caption: str, adet: int = 3) -> list[str]:
    m = re.search(r"/products/([a-z0-9\-]+)", caption)
    if not m:
        return []
    try:
        with urllib.request.urlopen(f"{STORE}/products/{m.group(1)}.json", timeout=20) as r:
            urun = json.load(r)["product"]
    except Exception as e:  # urun kaldirilmis olabilir — sadece kapakla devam
        print(f"   ürün görseli alınamadı ({m.group(1)}): {e}")
        return []
    return [i["src"] for i in urun.get("images", [])[1 : adet + 1]]


def _basliklar(caption: str) -> list[str]:
    satirlar = [s.strip() for s in caption.splitlines() if s.strip()]
    ad = re.sub(r"^[^\wÇĞİÖŞÜçğıöşü]+", "", satirlar[0]) if satirlar else ""
    cumle = ""
    for s in satirlar[1:]:
        if s.startswith(("#", "Hemen", "👉")) or "http" in s:
            continue
        # Ilk yan cumleden en fazla 6 kelime; sonda baglac/edat kalmasin.
        kel = re.split(r"[,;.!?]", s)[0].split()[:6]
        while kel and kel[-1].lower() in ("ve", "ile", "için", "bu", "olarak", "da", "de", "bir"):
            kel.pop()
        cumle = " ".join(kel)
        break
    return [ad[:60], cumle, "Aynı gün kargo", "Sipariş: profildeki link"]


def adaylar(bugun: str) -> list[pathlib.Path]:
    out = []
    for f in sorted((KOK / "posts").glob("*.md")):
        if f.name[:10] < bugun:
            continue
        m = FM_RE.match(f.read_text(encoding="utf-8"))
        if not m:
            continue
        fm = m.group(1)
        if "instagram" not in fm or ".mp4" in fm or "media: [" in fm:
            continue
        tema = re.search(r"tema:\s*(\w+)", fm)
        if tema and tema.group(1) in TEMALAR:
            out.append(f)
    return out


def donustur(f: pathlib.Path, kuru: bool = False) -> bool:
    metin = f.read_text(encoding="utf-8")
    fm, govde = FM_RE.match(metin).groups()
    tema = re.search(r"tema:\s*(\w+)", fm).group(1)
    kapak = re.search(r"^media:\s*(\S+)\s*$", fm, re.M).group(1)
    ekler = _urun_gorselleri(govde)
    print(f"→ {f.stem}  [{tema}] kapak + {len(ekler)} ürün görseli")
    if kuru:
        return True
    cikti = pathlib.Path("posts/media/slayt") / f"{f.stem}.mp4"
    video_uretim.uret(
        [kapak] + ekler,
        KOK / cikti,
        _basliklar(govde),
        muzik=video_uretim.muzik_sec(f.stem),
        kanca=KANCA[tema],
    )
    fm2 = re.sub(r"^media:\s*\S+\s*$", f"media: {cikti.as_posix()}\nkapak_gorsel: {kapak}", fm, flags=re.M)
    f.write_text(f"---\n{fm2}\n---\n{govde}", encoding="utf-8", newline="\n")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug")
    ap.add_argument("--tumu", action="store_true")
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--bugun", default=dt.date.today().isoformat())
    a = ap.parse_args()
    import os
    os.chdir(KOK)
    if a.slug:
        hedef = [KOK / "posts" / f"{a.slug}.md"]
    else:
        hedef = adaylar(a.bugun)
    if not (a.slug or a.tumu or a.kuru):
        print(f"{len(hedef)} aday. --kuru / --slug / --tumu ver.")
        return 1
    for f in hedef:
        donustur(f, a.kuru)
    print(f"{len(hedef)} post işlendi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
