# -*- coding: utf-8 -*-
"""Amazon SP-API istemcisi (Amazon.com.tr, EU bolgesi).

Env: AMAZON_LWA_CLIENT_ID, AMAZON_LWA_CLIENT_SECRET, AMAZON_REFRESH_TOKEN,
     AMAZON_SELLER_ID (A3ISCNEY2SXL4A), AMAZON_MARKETPLACE_ID (A33AVAJ2PDY3EV),
     AMAZON_SPAPI_ENDPOINT (https://sellingpartnerapi-eu.amazon.com)
Uygulama: Solution Provider Portal > "Atolye Stok Merkezi" (self-authorize refresh token).
Roller: Product Listing, Inventory and Order Tracking, Selling Partner Insights.
Not: Siparis alici bilgileri (PII) kisitli rol istemedigimiz icin gelmez; kargoyu panelden veriyoruz.
"""
import os
import time

import requests

BASE = os.environ.get("AMAZON_SPAPI_ENDPOINT", "https://sellingpartnerapi-eu.amazon.com").rstrip("/")
MARKET = os.environ.get("AMAZON_MARKETPLACE_ID", "A33AVAJ2PDY3EV")
SELLER = os.environ.get("AMAZON_SELLER_ID", "A3ISCNEY2SXL4A")
_tok = {"v": None, "t": 0}


def access_token():
    if _tok["v"] and time.time() < _tok["t"] - 60:
        return _tok["v"]
    r = requests.post("https://api.amazon.com/auth/o2/token", data={
        "grant_type": "refresh_token", "refresh_token": os.environ["AMAZON_REFRESH_TOKEN"],
        "client_id": os.environ["AMAZON_LWA_CLIENT_ID"], "client_secret": os.environ["AMAZON_LWA_CLIENT_SECRET"]}, timeout=30)
    r.raise_for_status()
    d = r.json()
    _tok["v"], _tok["t"] = d["access_token"], time.time() + int(d.get("expires_in", 3600))
    return _tok["v"]


def _req(method, path, params=None, json=None, retry=3):
    for i in range(retry):
        r = requests.request(method, BASE + path, params=params, json=json, timeout=60,
                             headers={"x-amz-access-token": access_token(), "Content-Type": "application/json"})
        if r.status_code == 429 and i < retry - 1:
            time.sleep(2 * (i + 1)); continue
        return r
    return r


def get(path, **params):
    return _req("GET", path, params=params)


def put(path, body, **params):
    return _req("PUT", path, params=params, json=body)


def patch(path, body, **params):
    return _req("PATCH", path, params=params, json=body)


def delete(path, **params):
    return _req("DELETE", path, params=params)


# ---- siparisler ----
def orders(created_after, statuses=None):
    """Orders v0: tum sayfalari dolasir. created_after ISO8601 (ornek 2026-09-01T00:00:00Z)."""
    out, nt = [], None
    while True:
        p = {"MarketplaceIds": MARKET, "CreatedAfter": created_after}
        if statuses:
            p["OrderStatuses"] = ",".join(statuses)
        if nt:
            p = {"NextToken": nt}
        r = get("/orders/v0/orders", **p)
        if r.status_code != 200:
            print("  AMZ orders", r.status_code, r.text[:150]); break
        pl = r.json().get("payload", {})
        out += pl.get("Orders", [])
        nt = pl.get("NextToken")
        if not nt:
            break
    return out


def order_items(order_id):
    r = get("/orders/v0/orders/%s/orderItems" % order_id)
    if r.status_code != 200:
        print("  AMZ items", order_id, r.status_code, r.text[:120]); return []
    return r.json().get("payload", {}).get("OrderItems", [])


# ---- listeleme ----
def listing(sku, included="summaries,attributes,offers,fulfillmentAvailability,issues"):
    return get("/listings/2021-08-01/items/%s/%s" % (SELLER, sku), marketplaceIds=MARKET, includedData=included)


def listing_put(sku, product_type, attributes, requirements="LISTING"):
    body = {"productType": product_type, "requirements": requirements, "attributes": attributes}
    return put("/listings/2021-08-01/items/%s/%s" % (SELLER, sku), body, marketplaceIds=MARKET)


def listing_patch(sku, product_type, patches):
    body = {"productType": product_type, "patches": patches}
    return patch("/listings/2021-08-01/items/%s/%s" % (SELLER, sku), body, marketplaceIds=MARKET)


def stok_yaz(sku, adet, product_type="PRODUCT"):
    return listing_patch(sku, product_type, [{"op": "replace", "path": "/attributes/fulfillment_availability",
                                              "value": [{"fulfillment_channel_code": "DEFAULT", "quantity": int(adet)}]}])


def fiyat_yaz(sku, fiyat, product_type="PRODUCT"):
    return listing_patch(sku, product_type, [{"op": "replace", "path": "/attributes/purchasable_offer",
                                              "value": [{"marketplace_id": MARKET, "currency": "TRY",
                                                         "our_price": [{"schedule": [{"value_with_tax": float(fiyat)}]}]}]}])


# ---- katalog ----
def catalog_search(keywords=None, identifiers=None, id_type="EAN", page_size=10):
    p = {"marketplaceIds": MARKET, "pageSize": page_size, "includedData": "summaries,identifiers"}
    if identifiers:
        p["identifiers"] = ",".join(identifiers); p["identifiersType"] = id_type
    if keywords:
        p["keywords"] = keywords
    return get("/catalog/2022-04-01/items", **p)


def product_type_definition(product_type, requirements="LISTING"):
    return get("/definitions/2020-09-01/productTypes/%s" % product_type, marketplaceIds=MARKET,
               requirements=requirements, locale="tr_TR")


def product_type_search(keywords):
    return get("/definitions/2020-09-01/productTypes", marketplaceIds=MARKET, keywords=keywords, locale="tr_TR")
