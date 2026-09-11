# -*- coding: utf-8 -*-
"""Amazon'da verilen SKU'lari yeni fiyata ceker (BuyBox rekabeti icin).

    python tools/amazon_fiyat_guncelle.py            # kuru calisma
    python tools/amazon_fiyat_guncelle.py --uygula
"""
from __future__ import annotations
import argparse, json, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from src.marketplaces import amazon_client as az

# 12.09.2026 BuyBox analizi: rakip BuyBox fiyatinin 1 TL alti (kar >= 25 TL)
HEDEF = {
    "AEUNOR3": 469.60, "AE16X2LCD": 321.70, "AELHMPMP": 250.99, "AEXL6009": 230.35,
    "AETP4056": 196.40, "AEACDMMR": 233.40, "AEHCSR04": 213.90, "AETKRM5V": 206.50,
    "AEL298N": 229.80, "AEHCSR501": 205.99, "AE28BYJ48": 214.50,
}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    a = ap.parse_args()
    sonuc = []
    for sk, yeni in HEDEF.items():
        amz_sku = "AEMZN-" + sk
        r = az.listing(amz_sku)
        if r.status_code != 200:
            print(f"{sk:14s} ILAN OKUNAMADI {r.status_code}"); continue
        j = r.json()
        pt = (j.get("summaries") or [{}])[0].get("productType")
        eski = (j.get("offers") or [{}])[0].get("price", {}).get("amount")
        print(f"{sk:14s} {eski:>8} -> {yeni:>8}  ({pt})")
        if not a.uygula:
            continue
        rr = az.fiyat_yaz(amz_sku, yeni, product_type=pt)
        jj = rr.json() if hasattr(rr, "json") else {}
        hata = [i for i in (jj.get("issues") or []) if i.get("severity") == "ERROR"]
        print(f"   -> {jj.get('status')} {('HATA ' + json.dumps(hata, ensure_ascii=False)) if hata else ''}")
        sonuc.append({"sk": sk, "eski": eski, "yeni": yeni, "durum": jj.get("status"), "hata": hata})
        time.sleep(1.0)
    if a.uygula:
        json.dump(sonuc, open(pathlib.Path(__file__).resolve().parents[1] / "content" / "amazon_fiyat_guncelleme.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\nguncellenen:", sum(1 for x in sonuc if x["durum"] == "ACCEPTED"), "/", len(sonuc))
    else:
        print("\n--- KURU CALISMA --- uygulamak icin --uygula")
    return 0

if __name__ == "__main__":
    sys.exit(main())
