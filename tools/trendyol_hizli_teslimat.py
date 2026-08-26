# -*- coding: utf-8 -*-
"""Hizli teslimata uygun olmayan Trendyol urunlerini uygun hale getirir.

Trendyol paneli (Hizli Teslimat & Operasyon) "sevkiyat surelerini 1 olarak
guncellemeniz yeterli" diyor. API tarafinda kural su: fastDeliveryType
tanimlayabilmek icin deliveryDuration = 1 olmali.

DIKKAT: updateProduct'ta gonderilmeyen alanlar varsayilana doner. Bu yuzden
payload, urunun API'den okunan MEVCUT degerleriyle eksiksiz kurulur; sadece
teslimat alanlari eklenir.

    python tools/trendyol_hizli_teslimat.py            # kuru calisma (gondermez)
    python tools/trendyol_hizli_teslimat.py --uygula   # gercekten gonderir
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import requests

from src.marketplaces import trendyol_client as tc

KARGO_ID = 9          # SURATMP - content/trendyol_yeni_urunler.json ile ayni
KESIM_SAATI = "14:00"  # mevcut 79 urunde kullanilan kesim saati
TIP = "SAME_DAY_SHIPPING"   # panelde "Bugun Kargoda"


def uygun_degil(varyant: dict) -> bool:
    return not (varyant.get("deliveryOptions") or {}).get("isRushDelivery")


def payload_kur(urun: dict, varyant: dict) -> dict:
    """Urunun mevcut bilgileriyle tam guncelleme payload'i kurar."""
    return {
        "barcode": varyant.get("barcode"),
        "title": urun.get("title"),
        "productMainId": urun.get("productMainId"),
        "brandId": (urun.get("brand") or {}).get("id"),
        "categoryId": (urun.get("category") or {}).get("id"),
        "stockCode": varyant.get("stockCode"),
        "dimensionalWeight": varyant.get("dimensionalWeight"),
        "description": urun.get("description"),
        "currencyType": "TRY",
        "vatRate": varyant.get("vatRate"),
        "cargoCompanyId": KARGO_ID,
        "images": [{"url": g.get("url")} for g in (urun.get("images") or []) if g.get("url")],
        "attributes": [
            {"attributeId": a["attributeId"], "attributeValueId": a["attributeValueId"]}
            for a in (urun.get("attributes") or [])
            if a.get("attributeId") and a.get("attributeValueId")
        ],
        # Asil degisiklik: termin 1 gun + ayni gun kargo etiketi
        "deliveryDuration": 1,
        "deliveryOption": {
            "deliveryDuration": 1,
            "fastDeliveryType": TIP,
        },
    }


def topla():
    hedef = []
    for _, urun in tc.iter_all_products(size=100):
        for varyant in (urun.get("variants") or []):
            if uygun_degil(varyant):
                hedef.append((urun, varyant))
    return hedef


def gonder(items: list[dict]) -> dict:
    url = f"{tc.BASE_URL}/product/sellers/{tc.SUPPLIER_ID}/products"
    r = requests.put(url, headers=tc._auth_header(), json={"items": items}, timeout=60)
    r.raise_for_status()
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true", help="gercekten gonder (yoksa kuru calisir)")
    ap.add_argument("--adet", type=int, default=0, help="sadece ilk N urunu isle (deneme icin)")
    a = ap.parse_args()

    hedef = topla()
    print(f"Hizli teslimata uygun olmayan varyant: {len(hedef)}\n")
    if not hedef:
        return 0

    if a.adet:
        hedef = hedef[: a.adet]
        print(f"(sadece ilk {len(hedef)} tanesi islenecek)\n")

    items = []
    eksikli = []
    for urun, varyant in hedef:
        p = payload_kur(urun, varyant)
        eksik = [k for k in ("barcode", "title", "productMainId", "brandId", "categoryId",
                             "stockCode", "dimensionalWeight", "description", "vatRate")
                 if not p.get(k)]
        if not p["images"]:
            eksik.append("images")
        if eksik:
            eksikli.append((p.get("stockCode"), eksik))
            continue
        items.append(p)

    if eksikli:
        print("!! Eksik alani olan urunler atlandi:")
        for sc, e in eksikli:
            print(f"   {sc}: {', '.join(e)}")
        print()

    print(f"Gonderilecek: {len(items)} urun")
    for p in items[:5]:
        print(f"   {p['stockCode']:16s} {str(p['title'])[:44]}")
    if len(items) > 5:
        print(f"   ... ve {len(items)-5} tane daha")

    if not a.uygula:
        print("\n--- KURU CALISMA - hicbir sey gonderilmedi ---")
        print("Ornek payload:")
        if items:
            ornek = dict(items[0])
            ornek["description"] = (ornek.get("description") or "")[:60] + "..."
            print(json.dumps(ornek, ensure_ascii=False, indent=2)[:1200])
        print("\nGercekten uygulamak icin: --uygula")
        return 0

    # Trendyol istek basina en fazla 1000 item aliyor; yine de gruplayalim.
    for i in range(0, len(items), 100):
        obek = items[i : i + 100]
        sonuc = gonder(obek)
        print(f"gonderildi ({len(obek)} urun) -> {sonuc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
