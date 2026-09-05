# -*- coding: utf-8 -*-
"""Kanallardan yeni siparisleri toplar, receteyle parca stogundan duser, kanallara dagitir.

Akis:  kanal siparisleri -> (gorulmemis olanlar) -> kalem {kod, adet} -> Recete.parcalar
       -> Shopify parca stogu (stok_dus) -> merkez.hedef_stoklar -> merkez.dagit
Durum: state/siparis_gorulen.json  {kanal: {siparisNo: tarih}}  (ayni siparis iki kez dusulmez)
Kayit: state/siparis_gunlugu.jsonl (her dusum bir satir)

Kullanim (kokten, PYTHONPATH="src;src/marketplaces"):
    python -m stok.siparis --kuru            # ne dusulecegini goster, hicbir sey yazma
    python -m stok.siparis --uygula          # Shopify'dan dus + kanallara dagit
    python -m stok.siparis --kanal trendyol --kuru
    python -m stok.siparis --tohum           # mevcut siparisleri 'gorulmus' isaretle (ilk kurulum)
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "src"))
sys.path.insert(0, os.path.join(KOK, "src", "marketplaces"))
GORULEN = os.path.join(KOK, "state", "siparis_gorulen.json")
GUNLUK = os.path.join(KOK, "state", "siparis_gunlugu.jsonl")
IPTAL = {"cancelled", "canceled", "iptal", "returned", "unsupplied", "undelivered", "iade"}


def _ilk(d, *anahtarlar, vars=None):
    for a in anahtarlar:
        if isinstance(d, dict) and d.get(a) not in (None, ""):
            return d[a]
    return vars


def _kalemler(o):
    """Bir siparis nesnesinden [{kod, barkod, adet}] cikarir (kanal bagimsiz, anahtar adaylariyla)."""
    for lk in ("lines", "items", "lineItems", "orderItems", "orderLines", "products"):
        L = o.get(lk) if isinstance(o, dict) else None
        if isinstance(L, list) and L:
            out = []
            for x in L:
                if not isinstance(x, dict):
                    continue
                durum = str(_ilk(x, "orderLineItemStatusName", "status", "lineStatus", vars="") or "").lower()
                if durum in IPTAL:
                    continue
                out.append({
                    "kod": _ilk(x, "merchantSku", "merchantSKU", "stockCode", "sellerStockCode", "vendorStockCode", "productCode", "code", "sku"),
                    "barkod": _ilk(x, "barcode", "Barcode", "ean", "gtin"),
                    "adet": int(_ilk(x, "quantity", "Quantity", "amount", "count", vars=1) or 1),
                })
            return out
    return []


# ---------------- kanal toplayicilar: her biri [{no, tarih, durum, kalemler}] ----------------
def topla_trendyol(gun=14):
    import trendyol_client as tc
    out = []
    son = int(time.time() * 1000)
    bas = son - gun * 86400000
    for p in range(10):
        r = tc.get_orders(start_date_ms=bas, end_date_ms=son, page=p, size=100)
        d = r if isinstance(r, dict) else r.json()
        L = d.get("content") or []
        for o in L:
            out.append({"no": str(o["orderNumber"]), "tarih": o.get("orderDate"),
                        "durum": o.get("status"), "kalemler": _kalemler(o)})
        if len(L) < 100:
            break
    return out


def topla_hepsiburada():
    import hepsiburada_client as hb
    out = []
    for fn in (hb.get_new_order_items, hb.get_unpacked_packages, hb.get_packages):
        try:
            r = fn(offset=0, limit=100)
        except Exception as e:  # kimlik yoksa vb.
            print("  HB", fn.__name__, "hata:", str(e)[:120])
            continue
        # HB /orders ucu kalem bazli doner (her item bir siparis satiri, merchantSKU + quantity);
        # /packages uclari paket doner (items listesi icinde). Siparis no'ya gore grupla.
        grup = {}
        L = r if isinstance(r, list) else (r.get("items") or [])
        for o in L:
            no = str(_ilk(o, "orderNumber", "OrderNumber", "PackageNumber", "id", "Id"))
            g = grup.setdefault(no, {"no": no, "tarih": _ilk(o, "orderDate", "OrderDate", "createdDate"),
                                     "durum": _ilk(o, "status", "Status", vars=fn.__name__), "kalemler": []})
            kl = _kalemler(o)
            if not kl and _ilk(o, "merchantSKU", "merchantSku"):
                kl = _kalemler({"lines": [o]})
            g["kalemler"].extend(kl)
        out.extend(grup.values())
    return out


def topla_n11():
    import n11_client as n11
    out = []
    for st in ("Created", "Picking", "Shipped"):
        r = n11.get("/rest/delivery/v1/shipmentPackages", status=st, page=0, size=100)
        if r.status_code != 200:
            print("  N11", st, r.status_code)
            continue
        for o in (r.json().get("content") or []):
            out.append({"no": str(_ilk(o, "orderNumber", "id", "packageId")), "tarih": _ilk(o, "orderDate", "createdDate"),
                        "durum": st, "kalemler": _kalemler(o)})
    return out


def topla_pazarama(gun=14):
    from marketplaces import pazarama_client as pz
    out = []
    b = (datetime.now() - timedelta(days=gun)).strftime("%Y-%m-%d")
    s = datetime.now().strftime("%Y-%m-%d")
    r = pz.post("/order/getOrdersForApi", {"startDate": b, "endDate": s})
    if r.status_code != 200:
        print("  PZ", r.status_code, r.text[:120])
        return out
    for o in (r.json().get("data") or []):
        out.append({"no": str(_ilk(o, "orderNumber", "orderId", "id")), "tarih": _ilk(o, "orderDate", "createdDate"),
                    "durum": _ilk(o, "orderStatus", "status"), "kalemler": _kalemler(o)})
    return out


def topla_idefix():
    from marketplaces import idefix_client as ix
    out = []
    r = ix.get("/oms/%s/list" % os.environ["IDEFIX_SATICI_ID"])
    if r.status_code != 200:
        print("  IDX", r.status_code, r.text[:120])
        return out
    for o in (r.json().get("items") or []):
        out.append({"no": str(_ilk(o, "orderNumber", "orderId", "id", "shipmentId")), "tarih": _ilk(o, "orderDate", "createdAt"),
                    "durum": _ilk(o, "status", "orderStatus"), "kalemler": _kalemler(o)})
    return out


TOPLAYICI = {"trendyol": topla_trendyol, "hepsiburada": topla_hepsiburada, "n11": topla_n11,
             "pazarama": topla_pazarama, "idefix": topla_idefix}
# pttavm: Api-Key/Access-Token gelince (EN-5313) eklenecek


# ---------------- durum ----------------
def gorulen_oku():
    try:
        return json.load(open(GORULEN, encoding="utf-8"))
    except FileNotFoundError:
        return {}


def gorulen_yaz(g):
    json.dump(g, open(GORULEN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def gunluk(kayit):
    with open(GUNLUK, "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")


def barkod_haritasi():
    """barkod -> kanal stok kodu (kod gelmeyen kalemler icin)."""
    h = {}
    try:
        for u in json.load(open(os.path.join(KOK, "content", "n11_urunler.json"), encoding="utf-8")):
            if u.get("barkod"):
                h[str(u["barkod"])] = u.get("tyStokKodu") or u["stokKodu"]
    except FileNotFoundError:
        pass
    try:
        for u in json.load(open(os.path.join(KOK, "state", "ty_katalog_snapshot.json"), encoding="utf-8")):
            if u.get("barcode") and u.get("stockCode"):
                h.setdefault(str(u["barcode"]), u["stockCode"])
    except FileNotFoundError:
        pass
    return h


def yeni_siparisler(kanallar):
    g = gorulen_oku()
    yeni = []
    for k in kanallar:
        try:
            L = TOPLAYICI[k]()
        except Exception as e:
            print("  %s toplama hatasi: %s" % (k, str(e)[:160]))
            continue
        gk = g.setdefault(k, {})
        n_yeni = 0
        for o in L:
            if o["no"] in gk or str(o.get("durum", "")).lower() in IPTAL:
                continue
            o["kanal"] = k
            yeni.append(o)
            n_yeni += 1
        print("  %-12s %3d siparis, %d yeni" % (k, len(L), n_yeni))
    return yeni, g


def main():
    a = sys.argv[1:]
    kuru = "--uygula" not in a
    kanallar = [a[a.index("--kanal") + 1]] if "--kanal" in a else list(TOPLAYICI)
    from stok.recete import Recete
    from stok import merkez
    R = Recete()
    bh = barkod_haritasi()

    if "--tohum" in a:
        g = gorulen_oku()
        for k in kanallar:
            try:
                for o in TOPLAYICI[k]():
                    g.setdefault(k, {})[o["no"]] = str(o.get("tarih"))
            except Exception as e:
                print("  %s: %s" % (k, str(e)[:120]))
        gorulen_yaz(g)
        print("tohumlandi:", {k: len(v) for k, v in g.items()})
        return

    print("siparisler toplaniyor (%s)..." % ("KURU" if kuru else "UYGULA"))
    yeni, g = yeni_siparisler(kanallar)
    if not yeni:
        print("yeni siparis yok")
        return

    parca = merkez.parca_stoklari()
    toplam_dusum, etkilenen = {}, set()
    for o in yeni:
        for kl in o["kalemler"]:
            kod = kl["kod"] or bh.get(str(kl["barkod"]))
            if not kod:
                print("  ! %s %s: kod cozulemedi %s" % (o["kanal"], o["no"], kl))
                continue
            sh = R.kanonik(kod)
            if sh not in parca and sh not in R.setler:
                print("  ! %s %s: '%s' Shopify'da/recetede yok (alias ekle: content/shopify_sku.json)" % (o["kanal"], o["no"], kod))
                gunluk({"an": datetime.now().isoformat(timespec="minutes"), "kanal": o["kanal"], "no": o["no"],
                        "kod": kod, "adet": kl["adet"], "hata": "bilinmeyen kod", "kuru": kuru})
                continue
            ihtiyac, etk = R.satis_dus(sh, kl["adet"], parca)
            for p, n in ihtiyac.items():
                toplam_dusum[p] = toplam_dusum.get(p, 0) + n
            etkilenen.update(etk)
            print("  %-12s %-14s %-14s x%d -> %s" % (o["kanal"], o["no"], sh, kl["adet"],
                                                   ", ".join("%s-%d" % (p, n) for p, n in ihtiyac.items())))
            gunluk({"an": datetime.now().isoformat(timespec="minutes"), "kanal": o["kanal"], "no": o["no"],
                    "kod": sh, "adet": kl["adet"], "dusum": ihtiyac, "kuru": kuru})
        g.setdefault(o["kanal"], {})[o["no"]] = str(o.get("tarih"))

    print("\nparca dusumu:", toplam_dusum)
    print("etkilenen set:", sorted(etkilenen))
    hedef = merkez.hedef_stoklar(R, parca)
    kritik = {k: parca.get(k) for k in toplam_dusum if (parca.get(k) or 0) <= merkez.KRITIK_ESIK}
    try:
        from stok import bildirim
        bildirim.siparis_bildir(yeni, toplam_dusum, kritik, kuru=kuru)
    except Exception as e:
        print("bildirim hatasi:", str(e)[:120])
    if kuru:
        print("(kuru: Shopify'a ve kanallara yazilmadi, gorulen listesi guncellenmedi)")
        return
    try:
        from stok import shopify_admin
        print("Shopify dusum:", shopify_admin.stok_dus(toplam_dusum, sebep="shrinkage"))
    except Exception as e:
        print("Shopify yazilamadi:", str(e)[:160])
    print(merkez.dagit(hedef, list(merkez.KANALLAR) if hasattr(merkez, "KANALLAR") else None, kuru=False))
    gorulen_yaz(g)


if __name__ == "__main__":
    main()
