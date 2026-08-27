# -*- coding: utf-8 -*-
"""Defter urunlerinin TY aciklamalarini gunceller.

DIKKAT: updateProduct'ta gonderilmeyen alanlar varsayilana doner. Bu yuzden
payload, urunun API'den okunan MEVCUT degerleriyle eksiksiz kurulur; sadece
description degistirilir. (trendyol_hizli_teslimat.py ile ayni desen.)

    python tools/trendyol_defter_aciklama.py            # kuru calisma
    python tools/trendyol_defter_aciklama.py --uygula   # gercekten gonderir
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import requests

from src.marketplaces import trendyol_client as tc
from tools.defter_aciklama import AILE, metin


def html(duz: str) -> str:  # kullanilmiyor (metin zaten HTML)
    """Duz metni TY'nin kabul ettigi basit HTML'e cevirir."""
    parcalar = []
    for satir in duz.split("\n"):
        s = satir.strip()
        if not s:
            continue
        if s.startswith("- "):
            parcalar.append(f"<li>{s[2:]}</li>")
        else:
            parcalar.append(f"<p>{s}</p>")
    # ardisik li'leri ul icine al
    cikti, tampon = [], []
    for p in parcalar:
        if p.startswith("<li>"):
            tampon.append(p)
        else:
            if tampon:
                cikti.append("<ul>" + "".join(tampon) + "</ul>")
                tampon = []
            cikti.append(p)
    if tampon:
        cikti.append("<ul>" + "".join(tampon) + "</ul>")
    return "".join(cikti)


def payload_kur(urun: dict, varyant: dict, aciklama: str) -> dict:
    p = {
        "barcode": varyant.get("barcode"),
        "title": urun.get("title"),
        "productMainId": urun.get("productMainId"),
        "brandId": (urun.get("brand") or {}).get("id"),
        "categoryId": (urun.get("category") or {}).get("id"),
        "stockCode": varyant.get("stockCode"),
        "dimensionalWeight": varyant.get("dimensionalWeight"),
        "description": aciklama,
        "currencyType": "TRY",
        "vatRate": varyant.get("vatRate"),
        "cargoCompanyId": 9,
        "images": [{"url": g.get("url")} for g in (urun.get("images") or []) if g.get("url")],
        "attributes": [
            {"attributeId": a["attributeId"], "attributeValueId": a["attributeValueId"]}
            for a in (urun.get("attributes") or [])
            if a.get("attributeId") and a.get("attributeValueId")
        ],
    }
    # Sevkiyat suresini OLDUGU GIBI koru. fastDeliveryType yalnizca sure 1 ise
    # gonderilebiliyor; 2 gunluk urunlerde gonderilirse TY istegi reddediyor.
    sure = (varyant.get("deliveryOptions") or {}).get("deliveryDuration")         or varyant.get("deliveryDuration") or 1
    p["deliveryDuration"] = sure
    if sure == 1 and (varyant.get("deliveryOptions") or {}).get("isRushDelivery"):
        p["deliveryOption"] = {"deliveryDuration": 1,
                               "fastDeliveryType": "SAME_DAY_SHIPPING"}
    return p


def tekli_metinleri() -> dict:
    """Tekli aciklamalarin ORIJINAL hali (dosyadan).

    Canli TY'den okumak YANLIS: TY zaten bu sablonla guncellendi, tekrar
    uygulamak paket bloklarini ve yaprak satirini ikinci kez ekler.
    """
    import json
    kaynak = pathlib.Path(__file__).resolve().parent / "defter_tekli_kaynak.json"
    ham = json.loads(kaynak.read_text(encoding="utf-8"))
    return {"isdosyasi": ham["AESTJDFTR"], "temrin": ham["AETEMDEF"]}


TEKLI = {}


def main() -> int:
    global TEKLI
    TEKLI = tekli_metinleri()
    if len(TEKLI) < 2:
        print("Tekli aciklamalar okunamadi:", list(TEKLI))
        return 1
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    # Saglam urunleri bos yere guncellememek icin: TY urun guncellemesi
    # onay surecini yeniden tetikleyebiliyor, gereksiz risk alinmaz.
    ap.add_argument("--stok", nargs="*", default=None,
                    help="sadece bu stok kodlarini guncelle")
    a = ap.parse_args()

    items, atlanan = [], []
    for _, urun in tc.iter_all_products(size=100):
        for v in (urun.get("variants") or []):
            sc = v.get("stockCode")
            if v.get("archived") or sc not in AILE:
                continue
            if a.stok and sc not in a.stok:
                continue
            yeni = metin(sc, TEKLI[AILE[sc]])
            p = payload_kur(urun, v, yeni)
            eksik = [k for k in ("barcode", "title", "productMainId", "brandId",
                                 "categoryId", "stockCode", "dimensionalWeight",
                                 "description", "vatRate") if not p.get(k)]
            if not p["images"]:
                eksik.append("images")
            if eksik:
                atlanan.append((sc, eksik))
                continue
            items.append(p)
            print(f"  {sc:14s} aciklama {len(urun.get('description') or '')} -> {len(yeni)} karakter")

    if atlanan:
        print("\n!! Eksik alani olan urunler atlandi:")
        for sc, e in atlanan:
            print(f"   {sc}: {', '.join(e)}")

    print(f"\nGuncellenecek urun: {len(items)}")
    if not a.uygula:
        print("--- KURU CALISMA --- gercekten gondermek icin: --uygula")
        return 0

    url = f"{tc.BASE_URL}/product/sellers/{tc.SUPPLIER_ID}/products"
    r = requests.put(url, headers=tc._auth_header(), json={"items": items}, timeout=60)
    r.raise_for_status()
    print("gonderildi ->", r.json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
