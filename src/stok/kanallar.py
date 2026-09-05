# -*- coding: utf-8 -*-
"""Kanal stok adaptorleri. Her fonksiyon: stok_bas_<kanal>(hedef, kuru) -> ozet.

hedef: {shopify_sku: adet}. Kanal kodlari alias tablosuyla cozulur
(content/shopify_sku.json 'alias': kanal kodu -> shopify sku). Barkod gereken
kanallar (TY, Idefix, PttAVM) icin content/n11_urunler.json ve TY katalog
anlik goruntusu kullanilir.
"""
import json
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "src"))
sys.path.insert(0, os.path.join(KOK, "src", "marketplaces"))


def _alias_ters():
    S = json.load(open(os.path.join(KOK, "content", "shopify_sku.json"), encoding="utf-8"))
    ters = {}
    for a, b in S.get("alias", {}).items():
        if b:
            ters.setdefault(b, []).append(a)
    return ters


def _kanal_kodlari(hedef):
    """{kanal_stok_kodu: adet} — Shopify SKU'sunu kanal kodlarina acar (alias tersi + kendisi)."""
    ters = _alias_ters()
    out = {}
    for sku, adet in hedef.items():
        if adet is None:
            continue
        for kod in [sku] + ters.get(sku, []):
            out[kod] = adet
    return out


def _barkodlar():
    """kanal stok kodu -> {ty: TY barkodu, ean: 13 haneli}"""
    b = {}
    try:
        for u in json.load(open(os.path.join(KOK, "state", "ty_katalog_snapshot.json"), encoding="utf-8")):
            if u.get("stockCode"):
                b.setdefault(u["stockCode"], {})["ty"] = u.get("barcode")
    except FileNotFoundError:
        pass
    for u in json.load(open(os.path.join(KOK, "content", "n11_urunler.json"), encoding="utf-8")):
        sk = u.get("tyStokKodu") or u["stokKodu"]
        b.setdefault(sk, {})["ean"] = str(u.get("barkod") or "")
    return b


# ---------------- Trendyol: barkod + quantity ----------------
def stok_bas_trendyol(hedef, kuru=True):
    import trendyol_client as tc
    bk = _barkodlar()
    items = [{"barcode": bk[k]["ty"], "quantity": int(v)} for k, v in _kanal_kodlari(hedef).items()
             if k in bk and bk[k].get("ty")]
    if kuru:
        return "kuru: %d barkod" % len(items)
    sonuc = []
    for i in range(0, len(items), 100):
        sonuc.append(tc.update_price_and_inventory(items[i:i + 100]))
    return sonuc


# ---------------- Hepsiburada: merchantSku + availableStock ----------------
def stok_bas_hepsiburada(hedef, kuru=True):
    import hepsiburada_client as hb
    items = [{"merchantSku": k, "availableStock": int(v)} for k, v in _kanal_kodlari(hedef).items()]
    if kuru:
        return "kuru: %d sku" % len(items)
    return hb.update_stock(items)


# ---------------- N11: stockCode + quantity (max 1000) ----------------
def stok_bas_n11(hedef, kuru=True):
    import n11_client as n11
    items = [{"stockCode": k, "quantity": int(v)} for k, v in _kanal_kodlari(hedef).items()]
    if kuru:
        return "kuru: %d stok kodu" % len(items)
    return n11.post("/ms/product/tasks/price-stock-update", {"payload": {"skus": items}})


# ---------------- Idefix: barcode + inventoryQuantity ----------------
def stok_bas_idefix(hedef, kuru=True):
    from marketplaces import idefix_client as ix
    bk = _barkodlar()
    items = [{"barcode": bk[k]["ean"], "inventoryQuantity": int(v)} for k, v in _kanal_kodlari(hedef).items()
             if k in bk and bk[k].get("ean")]
    if kuru:
        return "kuru: %d barkod" % len(items)
    return ix.post("/pim/catalog/%s/inventory-upload" % os.environ["IDEFIX_SATICI_ID"], {"items": items}).json()


# ---------------- PttAVM: barcode + stock (max 1000, ayni istek 5 dk'da bir) ----------------
def stok_bas_pttavm(hedef, kuru=True):
    import uuid
    import requests
    bk = _barkodlar()
    items = [{"barcode": bk[k]["ean"], "stock": int(v)} for k, v in _kanal_kodlari(hedef).items()
             if k in bk and bk[k].get("ean")]
    if kuru:
        return "kuru: %d barkod" % len(items)
    h = {"Api-Key": os.environ["PTTAVM_API_KEY"], "Access-Token": os.environ["PTTAVM_ACCESS_TOKEN"],
         "Content-Type": "application/json", "X-Correlation-Id": str(uuid.uuid4())}
    r = requests.post("https://integration-api.pttavm.com/api/v1/products/stock-prices", headers=h,
                      json={"items": items}, timeout=60)
    return r.status_code, r.text[:300]


# ---------------- Pazarama: POST /product/updateStock-v2 {items:[{code: BARKOD, stockCount}]} ----------------
def _pazarama_barkodlari():
    """stokKodu -> Pazarama barkodu (code). state/pazarama_katalog.json'dan; yoksa API'den ceker."""
    from marketplaces import pazarama_client as pc
    yol = os.path.join(KOK, "state", "pazarama_katalog.json")
    try:
        return json.load(open(yol, encoding="utf-8"))
    except FileNotFoundError:
        pass
    g = {}
    for y in ("/product/products/approved", "/product/products/unapproved"):
        for p in range(8):
            d = pc.get(y, Size=100, Page=p).json().get("data")
            l = (d or {}).get("sellerProducts") if isinstance(d, dict) else (d or [])
            l = l or []
            yeni = 0
            for x in l:
                if x["stockCode"] not in g:
                    g[x["stockCode"]] = x["code"]; yeni += 1
            if yeni == 0 or len(l) < 100:
                break
    json.dump(g, open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return g


def stok_bas_pazarama(hedef, kuru=True):
    from marketplaces import pazarama_client as pc
    bk = _pazarama_barkodlari()
    items = [{"code": bk[k], "stockCount": int(v)} for k, v in _kanal_kodlari(hedef).items() if k in bk]
    if kuru:
        return "kuru: %d barkod" % len(items)
    r = pc.post("/product/updateStock-v2", {"items": items})
    return r.status_code, r.text[:300]
