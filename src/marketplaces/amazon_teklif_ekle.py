# -*- coding: utf-8 -*-
"""Amazon'da ZATEN VAR OLAN urunlere (ASIN) teklif ekler (merchant_suggested_asin yolu; barkod/GTIN gerekmez).

Kaynak: content/amazon_teklif.json  [{"sku": "AEHCSR04E", "asin": "B0...", "fiyat": 249.0, "adet": 20}, ...]
Fiyat formulu (Amazon kargo satici oder, musteriye ucretsiz): (ty_fiyat + kargo(desi) + 6) / (1 - 0.095*1.2)
    kargo (Kolay Gonderi, KDV dahil): 1 desi 93, 2 desi 97, 3 desi 112, 4 desi 115, 5 desi 121
    python src/marketplaces/amazon_teklif_ekle.py --onizle   # VALIDATION_PREVIEW
    python src/marketplaces/amazon_teklif_ekle.py --gonder
"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import amazon_client as az

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KARGO = {1: 93.0, 2: 97.0, 3: 112.0, 4: 115.0, 5: 121.0, 6: 128.0}


def amazon_fiyat(ty_fiyat, desi, komisyon=0.095):
    d = max(1, int(round(float(desi or 1))))
    k = KARGO.get(d, 128.0 + (d - 6) * 8)
    return round((float(ty_fiyat) + k + 6) / (1 - komisyon * 1.2) + 0.49)  # tam TL'ye yuvarla


def product_type(asin):
    r = az.get("/catalog/2022-04-01/items/%s" % asin, marketplaceIds=az.MARKET, includedData="productTypes,summaries")
    j = r.json()
    pts = [p.get("productType") for p in j.get("productTypes", [])]
    ad = ((j.get("summaries") or [{}])[0]).get("itemName", "")
    return (pts[0] if pts else "PRODUCT"), ad


def body(sku, asin, fiyat, adet, pt):
    mk = az.MARKET
    return {"productType": pt, "requirements": "LISTING_OFFER_ONLY", "attributes": {
        "merchant_suggested_asin": [{"value": asin, "marketplace_id": mk}],
        "condition_type": [{"value": "new_new", "marketplace_id": mk}],
        "fulfillment_availability": [{"fulfillment_channel_code": "DEFAULT", "quantity": int(adet)}],
        "purchasable_offer": [{"marketplace_id": mk, "currency": "TRY", "our_price": [{"schedule": [{"value_with_tax": float(fiyat)}]}]}],
    }}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--onizle", action="store_true"); ap.add_argument("--gonder", action="store_true")
    ap.add_argument("--dosya", default=os.path.join(KOK, "content", "amazon_teklif.json")); ap.add_argument("--kod", nargs="*")
    a = ap.parse_args()
    liste = json.load(open(a.dosya, encoding="utf-8"))
    if a.kod: liste = [x for x in liste if x["sku"] in a.kod]
    for x in liste:
        pt, ad = product_type(x["asin"])
        sku = "AEMZN-" + x["sku"]
        b = body(sku, x["asin"], x["fiyat"], x.get("adet", 10), pt)
        params = {"marketplaceIds": az.MARKET}
        if a.onizle and not a.gonder: params["mode"] = "VALIDATION_PREVIEW"
        if not (a.onizle or a.gonder):
            print(sku, x["asin"], pt, x["fiyat"], "|", ad[:60]); continue
        r = az._req("PUT", "/listings/2021-08-01/items/%s/%s" % (az.SELLER, sku), params=params, json=b)
        j = r.json() if r.text else {}
        iss = [(i.get("severity"), i.get("code"), (i.get("message") or "")[:120]) for i in j.get("issues", [])]
        print("%-22s %s %s %s TL | %s | %s" % (sku, x["asin"], j.get("status"), x["fiyat"], ad[:45], [i for i in iss if i[0] == "ERROR"]))
        time.sleep(0.4)


if __name__ == "__main__":
    main()
