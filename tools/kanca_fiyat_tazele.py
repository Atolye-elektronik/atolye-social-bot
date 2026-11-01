# -*- coding: utf-8 -*-
"""Kuyruktaki kanca postlarının "Güncel fiyat" slaytını sitedeki fiyatla yeniden çizer.

01.11.2026: kanca carousel'leri Eylül'de üretilmişti; robot ve proje kitlerinin
fiyatı değişince 3 Aralık'a kadar sıradaki postlar eski fiyatı (RFID 649 vb.)
gösterecekti. Fiyat değiştiğinde bu araç çalıştırılır, değişen slaytlar
GitHub'a gönderilir (Instagram görseli raw URL'den çeker).

    python tools/kanca_fiyat_tazele.py          # yalnız rapor
    python tools/kanca_fiyat_tazele.py --uygula # slaytları yeniden çiz
"""
from __future__ import annotations

import io
import os
import pathlib
import re
import sys
from datetime import datetime

KOK = pathlib.Path(__file__).resolve().parents[1]
os.chdir(KOK)
sys.path[:0] = [str(KOK), str(KOK / "src")]
for _l in io.open(KOK / ".env", encoding="utf-8") if (KOK / ".env").exists() else []:
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        _a, _b = _l.split("=", 1)
        os.environ.setdefault(_a.strip(), _b.strip().strip('"').strip("'"))

from src import karusel_gorsel  # noqa: E402
from src.kanca_carousel import fiyat_satirlari  # noqa: E402
from stok import shopify_admin  # noqa: E402

Q = """query($h:String!){ productByIdentifier(identifier:{handle:$h}){ title handle status
  variants(first:10){ nodes{ title price availableForSale } } } }"""


def urun_getir(handle: str) -> dict | None:
    j = shopify_admin.gql(Q, {"h": handle})
    p = (j.get("data") or j).get("productByIdentifier")
    if not p:
        return None
    return {"title": p["title"], "handle": p["handle"], "status": p["status"],
            "variants": [{"title": v["title"], "price": v["price"], "available": v["availableForSale"]}
                         for v in p["variants"]["nodes"]]}


def main() -> int:
    uygula = "--uygula" in sys.argv
    bugun = datetime.now().strftime("%Y-%m-%d")
    degisen = 0
    for post in sorted(pathlib.Path("posts").glob("*.md")):
        if post.name[:10] < bugun:
            continue
        metin = post.read_text(encoding="utf-8")
        m = re.search(r"^media:\s*\[(.*)\]\s*$", metin, re.M)
        if not m:
            continue
        medya = [x.strip().replace("\\", "/") for x in m.group(1).split(",")]
        fiyat = [x for x in medya if re.search(r"/\d\d-fiyat\.png$", x)]
        h = re.findall(r"atolyeelektronik\.com/products/([A-Za-z0-9_-]+)", metin)
        if not fiyat or not h:
            continue
        urun = urun_getir(h[0])
        if not urun:
            print(f"! {post.name}: ürün bulunamadı ({h[0]})")
            continue
        yol = pathlib.Path(fiyat[0])
        sira = int(yol.name[:2])
        print(f"{post.name[:60]:60s} {urun['variants'][0]['price']:>9} ₺  {yol}")
        if uygula:
            with karusel_gorsel.Cizer() as cizer:
                cizer.satirlar("FİYAT", "Güncel fiyat", "", fiyat_satirlari(urun), cikti=yol,
                               alt_bilgi="1.200 ₺ üzeri kargo bedava", sayfa=(sira, len(medya)))
            degisen += 1
    print(f"{degisen} fiyat slaytı yeniden çizildi" if uygula else "--- rapor; çizmek için --uygula")
    return 0


if __name__ == "__main__":
    sys.exit(main())
