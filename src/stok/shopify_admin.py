# -*- coding: utf-8 -*-
"""Shopify Admin GraphQL — envanter okuma/yazma (stok masteri).

Gerekli env: SHOPIFY_STORE (orn. a3pnna-xy), SHOPIFY_ADMIN_TOKEN (custom app,
scope: read_products, read_inventory, write_inventory, read_orders).
Stok haritasi: content/shopify_sku.json (sku -> inventoryItem id). Yeni SKU'lar
`haritayi_yenile()` ile eklenir.
"""
import json
import os

import requests

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAGAZA = os.environ.get("SHOPIFY_STORE", "a3pnna-xy").strip()
TOKEN = os.environ.get("SHOPIFY_ADMIN_TOKEN", "").strip()
CLIENT_ID = os.environ.get("SHOPIFY_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("SHOPIFY_CLIENT_SECRET", "").strip()
SURUM = "2025-07"
URL = "https://%s.myshopify.com/admin/api/%s/graphql.json" % (MAGAZA, SURUM)
HARITA = os.path.join(KOK, "content", "shopify_sku.json")


_TOKEN_CACHE = {"token": TOKEN, "son": 0.0}


def token():
    """Sabit SHOPIFY_ADMIN_TOKEN varsa onu; yoksa Dev Dashboard uygulamasi icin client-credentials
    grant ile 24 saatlik token alir (SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET). 23 saatte bir yeniler."""
    import time
    if TOKEN:
        return TOKEN
    if not (CLIENT_ID and CLIENT_SECRET):
        raise RuntimeError("SHOPIFY_ADMIN_TOKEN veya SHOPIFY_CLIENT_ID/SECRET yok")
    if _TOKEN_CACHE["token"] and time.time() - _TOKEN_CACHE["son"] < 23 * 3600:
        return _TOKEN_CACHE["token"]
    r = requests.post("https://%s.myshopify.com/admin/oauth/access_token" % MAGAZA,
                      data={"grant_type": "client_credentials", "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
                      timeout=30)
    r.raise_for_status()
    _TOKEN_CACHE.update(token=r.json()["access_token"], son=time.time())
    return _TOKEN_CACHE["token"]


def gql(query, variables=None):
    r = requests.post(URL, headers={"X-Shopify-Access-Token": token(), "Content-Type": "application/json"},
                      json={"query": query, "variables": variables or {}}, timeout=60)
    r.raise_for_status()
    j = r.json()
    if j.get("errors"):
        raise RuntimeError(j["errors"])
    return j["data"]


def lokasyon_id():
    """Aktif lokasyon. read_locations kapsami olmadan: envanter seviyesi olan bir varyanttan okunur."""
    S = json.load(open(HARITA, encoding="utf-8"))["sku"]
    item = next(v["item"] for v in S.values() if v.get("item"))
    d = gql("{ inventoryItem(id:\"gid://shopify/InventoryItem/%d\"){ inventoryLevels(first:1){ nodes{ location{ id } } } } }" % item)
    return d["inventoryItem"]["inventoryLevels"]["nodes"][0]["location"]["id"]


def haritayi_yenile():
    """Tum varyantlari ceker, content/shopify_sku.json'i gunceller (alias tablosu korunur)."""
    q = """query($after:String){ products(first:50, after:$after){ pageInfo{hasNextPage endCursor}
      nodes{ status variants(first:20){ nodes{ id sku inventoryQuantity inventoryItem{ id tracked } } } } } }"""
    S = json.load(open(HARITA, encoding="utf-8"))
    sku = {}
    after = None
    while True:
        d = gql(q, {"after": after})["products"]
        for p in d["nodes"]:
            for v in p["variants"]["nodes"]:
                if not v["sku"] or v["sku"] in sku:
                    continue
                sku[v["sku"]] = {"variant": int(v["id"].split("/")[-1]),
                                 "item": int(v["inventoryItem"]["id"].split("/")[-1]),
                                 "qty": v["inventoryQuantity"], "status": p["status"],
                                 "tracked": v["inventoryItem"]["tracked"]}
        if not d["pageInfo"]["hasNextPage"]:
            break
        after = d["pageInfo"]["endCursor"]
    S["sku"] = sku
    json.dump(S, open(HARITA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return sku


def stoklari_oku():
    """{sku: qty} — canli."""
    return {k: v["qty"] for k, v in haritayi_yenile().items()}


def stok_yaz(degisiklikler, sebep="correction"):
    """degisiklikler: {sku: yeni_adet}. inventorySetQuantities ile mutlak yazar."""
    S = json.load(open(HARITA, encoding="utf-8"))["sku"]
    loc = lokasyon_id()
    q = """mutation($input: InventorySetQuantitiesInput!){ inventorySetQuantities(input:$input){
      userErrors{ field message } inventoryAdjustmentGroup{ changes{ name delta } } } }"""
    sonuc = []
    kalemler = [{"inventoryItemId": "gid://shopify/InventoryItem/%d" % S[k]["item"],
                 "locationId": loc, "quantity": int(v)} for k, v in degisiklikler.items() if k in S]
    for i in range(0, len(kalemler), 100):
        d = gql(q, {"input": {"name": "available", "reason": sebep, "ignoreCompareQuantity": True,
                              "quantities": kalemler[i:i + 100]}})
        sonuc.append(d["inventorySetQuantities"])
    return sonuc


def stok_dus(sku_adet, sebep="shrinkage"):
    """sku_adet: {sku: dusulecek_adet} — goreli ayarlama (satis dusumu)."""
    S = json.load(open(HARITA, encoding="utf-8"))["sku"]
    loc = lokasyon_id()
    q = """mutation($input: InventoryAdjustQuantitiesInput!){ inventoryAdjustQuantities(input:$input){
      userErrors{ field message } } }"""
    ch = [{"inventoryItemId": "gid://shopify/InventoryItem/%d" % S[k]["item"], "locationId": loc, "delta": -int(v)}
          for k, v in sku_adet.items() if k in S and v]
    if not ch:
        return None
    return gql(q, {"input": {"name": "available", "reason": sebep, "changes": ch}})["inventoryAdjustQuantities"]


if __name__ == "__main__":
    import sys
    if "--harita" in sys.argv:
        print(len(haritayi_yenile()), "sku yenilendi")
    else:
        print(json.dumps(stoklari_oku(), ensure_ascii=False)[:500])
