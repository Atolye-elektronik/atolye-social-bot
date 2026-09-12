# -*- coding: utf-8 -*-
"""Hesaplanan 'HB kar seviyesi' fiyatlarini N11 / PttAVM / Idefix / Amazon'a uygular.

Girdi: scratchpad/buybox/hb_seviye.json (tools/../scratchpad ... hb_seviye.py uretir)
Trendyol'a ve BuyBox urunlerine DOKUNMAZ (liste zaten haric tutulmus gelir).

    python tools/hb_seviye_uygula.py --kanal n11            # kuru calisma
    python tools/hb_seviye_uygula.py --kanal n11 --uygula
"""
from __future__ import annotations
import argparse, json, os, pathlib, re, sys, time

KOK = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK)); sys.path.insert(0, str(KOK / "src")); sys.path.insert(0, str(KOK / "src" / "marketplaces"))


def _env():
    for yol in (KOK / ".env", pathlib.Path("C:/Users/serdar/Desktop/atolyesocialbotmasaustu/.env")):
        if yol.exists():
            for l in open(yol, encoding="utf-8"):
                m = re.match(r"([A-Z0-9_]+)=(.*)", l.strip())
                if m:
                    os.environ.setdefault(m.group(1), m.group(2).strip().strip('"').strip("'"))


_env()
S = pathlib.Path("C:/Users/serdar/AppData/Local/Temp/claude/C--Users-serdar-Desktop-atolyesocialbotmasaustu/a4d0556e-5012-4f53-831e-17e87b486275/scratchpad/buybox")


def veri():
    return json.load(open(S / "hb_seviye.json", encoding="utf-8"))["satir"]


def n11_uygula(satir, uygula):
    import n11_client as n11
    d = n11.get("/ms/product-query", page=0, size=200).json().get("content") or []
    kod = {}
    for x in d:
        sk = str(x.get("stockCode") or "")
        t = sk
        for suf in ("-N11", "-AE"):
            if sk.endswith(suf):
                sk = sk[: -len(suf)]
        kod[sk] = t
    skus = []
    for s in satir:
        p = s.get("n11_yeni")
        if not p or s["sk"] not in kod:
            continue
        skus.append({"stockCode": kod[s["sk"]], "listPrice": round(p, 2), "salePrice": round(p, 2), "currencyType": "TL"})
        print(f"  {s['sk']:16s} {str(s.get('n11_simdi')):>8} -> {p:>8.2f}")
    print(f"N11: {len(skus)} urun")
    if uygula and skus:
        for i in range(0, len(skus), 50):
            r = n11.post("/ms/product/tasks/price-stock-update", {"payload": {"integrator": n11.ENTEGRATOR, "skus": skus[i:i + 50]}})
            print("   gonderim", r.status_code, r.text[:160])
            time.sleep(2)


def ptt_uygula(satir, uygula):
    import pttavm_client as ptt
    n11u = {(u.get("tyStokKodu") or u.get("stokKodu")): u for u in json.load(open(KOK / "content" / "n11_urunler.json", encoding="utf-8"))}
    ty = {x["stockCode"]: x for x in json.load(open(KOK / "state" / "trendyol_tam_katalog.json", encoding="utf-8")) if x.get("stockCode")}
    items = []
    for s in satir:
        p = s.get("ptt_yeni")
        if not p:
            continue
        bar = (n11u.get(s["sk"]) or {}).get("barkod") or (ty.get(s["sk"]) or {}).get("barcode")
        if not bar:
            print(f"  ! {s['sk']:16s} barkod yok, atlandi"); continue
        stok = int((ty.get(s["sk"]) or {}).get("quantity") or 10)
        items.append({"barcode": str(bar), "active": True, "quantity": stok,
                      "priceWithoutVAT": round(p / 1.2, 2), "priceWithVAT": round(p, 2),
                      "vatRate": 20, "discount": 0, "isCargoFromSupplier": False})
        print(f"  {s['sk']:16s} {str(s.get('ptt_simdi')):>8} -> {p:>8.2f}")
    print(f"PttAVM: {len(items)} urun")
    if uygula and items:
        for i in range(0, len(items), 50):
            r = ptt.post("/products/stock-prices", {"items": items[i:i + 50]})
            print("   gonderim", r.status_code, r.text[:200])
            time.sleep(3)


def idx_uygula(satir, uygula):
    """Idefix stok&fiyat gonderimi: POST /pim/catalog/{vendorId}/inventory-upload (developer.idefix.com)."""
    import idefix_client as ix
    tum = {x.get("vendorStockCode"): x for x in json.load(open(S / "idx_tum.json", encoding="utf-8"))}
    v = os.environ["IDEFIX_SATICI_ID"]
    items = []
    for s in satir:
        p = s.get("idx_yeni")
        x = tum.get(s["sk"])
        if not p or not x or not x.get("barcode"):
            continue
        items.append({"barcode": str(x["barcode"]), "price": round(p, 2), "comparePrice": round(p, 2),
                      "inventoryQuantity": int(x.get("inventoryQuantity") or 0),
                      "deliveryDuration": int(x.get("deliveryDuration") or 1),
                      "deliveryType": x.get("deliveryType") or "regular"})
        print(f"  {s['sk']:16s} {str(s.get('idx_simdi')):>8} -> {p:>8.2f}")
    print(f"Idefix: {len(items)} urun")
    if uygula and items:
        for i in range(0, len(items), 50):
            r = ix.post(f"/pim/catalog/{v}/inventory-upload", {"items": items[i:i + 50]})
            print("   gonderim", r.status_code, r.text[:200])
            time.sleep(2)


def amz_uygula(satir, uygula):
    from src.marketplaces import amazon_client as az
    n = 0
    for s in satir:
        p = s.get("amz_yeni")
        if not p:
            continue
        sku = "AEMZN-" + s["sk"]
        r = az.listing(sku)
        if r.status_code != 200:
            print(f"  ! {s['sk']} ilan okunamadi {r.status_code}"); continue
        j = r.json()
        pt = (j.get("summaries") or [{}])[0].get("productType")
        eski = (j.get("offers") or [{}])[0].get("price", {}).get("amount")
        print(f"  {s['sk']:16s} {str(eski):>8} -> {p:>8.2f}")
        n += 1
        if uygula:
            rr = az.fiyat_yaz(sku, round(p, 2), product_type=pt)
            jj = rr.json() if hasattr(rr, "json") else {}
            hata = [i for i in (jj.get("issues") or []) if i.get("severity") == "ERROR"]
            print(f"      {jj.get('status')} {hata if hata else ''}")
            time.sleep(1)
    print(f"Amazon: {n} urun")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kanal", required=True, choices=["n11", "ptt", "idx", "amz"])
    ap.add_argument("--uygula", action="store_true")
    a = ap.parse_args()
    satir = veri()
    {"n11": n11_uygula, "ptt": ptt_uygula, "idx": idx_uygula, "amz": amz_uygula}[a.kanal](satir, a.uygula)
    if not a.uygula:
        print("\n--- KURU CALISMA --- gondermek icin --uygula")
    return 0


if __name__ == "__main__":
    sys.exit(main())
