# -*- coding: utf-8 -*-
"""Kargo firmasi BOS kalmis Trendyol urunlerini Surat Kargo'ya (SURATMP, id 9) ceker.

12.09.2026 bulgusu: 140 onayli urunun 114'unde cargoProviders bos -> siparisler
Trendyol Express'e gidiyordu. Kullanici karari: "Trendyol'da hepsi Surat olmali".

updateProduct tam payload ister; payload trendyol_termin._payload ile urunun
mevcut degerlerinden kurulur (SURE=0 -> deliveryOption gonderilmez).

    python tools/trendyol_kargo_surat.py            # kuru calisma
    python tools/trendyol_kargo_surat.py --uygula   # gonder
    python tools/trendyol_kargo_surat.py --uygula --adet 1
"""
from __future__ import annotations
import argparse, json, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import requests
from src.marketplaces import trendyol_client as tc
import tools.trendyol_termin as tt

tt.SURE = 0

def topla():
    hedef = []
    for _, urun in tc.iter_all_products(size=100):
        if urun.get("archived"):
            continue
        for v in (urun.get("variants") or []):
            if v.get("archived") or v.get("onSale") is False:
                continue
            cps = v.get("cargoProviders") or urun.get("cargoProviders") or []
            if "SURATMP" not in cps:
                hedef.append((urun, v, cps))
    return hedef

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    ap.add_argument("--adet", type=int, default=0)
    a = ap.parse_args()
    hedef = topla()
    print(f"Surat olmayan varyant: {len(hedef)}")
    if a.adet:
        hedef = hedef[: a.adet]
    items, eksikli = [], []
    for urun, v, cps in hedef:
        p = tt.payload_kur(urun, v)
        # cargoCompanyId tek basina islemiyor; cargoProviders alani sart (12.09 denendi)
        p["cargoProviders"] = ["SURATMP"]
        eksik = [k for k in ("barcode","title","productMainId","brandId","categoryId","stockCode","dimensionalWeight","description","vatRate") if not p.get(k)]
        if not p["images"]:
            eksik.append("images")
        if eksik:
            eksikli.append((p.get("stockCode"), eksik)); continue
        items.append(p)
    for sc, e in eksikli:
        print(f"   atlandi {sc}: {', '.join(e)}")
    print(f"Gonderilecek: {len(items)}")
    for p in items[:8]:
        print(f"   {p['stockCode']:18s} {str(p['title'])[:50]}")
    if not a.uygula:
        print("--- KURU CALISMA ---")
        return 0
    for i in range(0, len(items), 100):
        obek = items[i:i+100]
        r = tt.gonder(obek)
        print(f"gonderildi ({len(obek)}) -> {r}")
        bid = r.get("batchRequestId")
        if bid:
            time.sleep(8)
            res = tc.get_batch_request_result(bid)
            st = res.get("status"); its = res.get("items") or []
            fails = [(x.get("requestItem",{}).get("stockCode") or x.get("requestItem",{}).get("barcode"), x.get("failureReasons")) for x in its if x.get("status") != "SUCCESS"]
            print(f"   batch {bid}: {st}, item {len(its)}, hatali {len(fails)}")
            for f in fails[:15]:
                print("   HATA", f)
    return 0

if __name__ == "__main__":
    sys.exit(main())
