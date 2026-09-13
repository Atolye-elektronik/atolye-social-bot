# -*- coding: utf-8 -*-
"""Tum kanallardaki CANLI stogu beklenen hedefle karsilastirir."""
import base64, json, os, re, sys, time
KOK = "C:/Users/serdar/Desktop/atolye-temiz"
sys.path.insert(0, KOK + "/src"); sys.path.insert(0, KOK + "/src/marketplaces")
for y in ("C:/Users/serdar/Desktop/atolyesocialbotmasaustu/.env", KOK + "/.env"):
    for l in open(y, encoding="utf-8"):
        m = re.match(r"([A-Z0-9_]+)=(.*)", l.strip())
        if m:
            os.environ.setdefault(m.group(1), m.group(2).strip().strip('"').strip("'"))
import requests  # noqa

from stok.recete import Recete  # noqa
from stok import merkez as _M  # noqa
H = _M.hedef_stoklar(Recete(), _M.parca_stoklari())   # kanallara basilan GERCEK hedef
S = json.load(open(KOK + "/content/shopify_sku.json", encoding="utf-8"))
ters = {}
for a, b in (S.get("alias") or {}).items():
    if b:
        ters.setdefault(b, []).append(a)
BEK = {}
for k, v in H.items():
    BEK[k] = v
    for u in ters.get(k, []):
        BEK[u] = v


def rapor(ad, canli):
    """canli: {kod: adet} ya da [(kod, barkod, adet)] - ikincisi mukerrer ilanlar icin."""
    ok, fark, ornek = 0, 0, []
    ciftler = canli if isinstance(canli, list) else [(k, None, v) for k, v in canli.items()]
    for k, bar, v in ciftler:
        b = BEK.get(k)
        if b is None:
            continue
        if int(v or 0) == int(b):
            ok += 1
        else:
            fark += 1
            if len(ornek) < 5:
                ornek.append("%s%s bekl %s canli %s" % (k, (" [%s]" % bar) if bar else "", b, v))
    isaret = "OK " if fark == 0 else "!! "
    print("%s%-13s dogrulanan %3d | UYUSMAYAN %3d  %s" % (isaret, ad, ok, fark, "; ".join(ornek)))


def shopify():
    from stok import shopify_admin as sa
    return sa.stoklari_oku()


def trendyol():
    """DIKKAT: sozluk yerine ILAN LISTESI dondurur.

    Ayni stok kodunda 2-3 aktif ilan var (mukerrer ilanlar). Sozluge yazinca
    sonuncusu onceki(leri)ni eziyor ve eski stokta kalan ilan dogrulamada
    GORUNMUYORDU (13.09). Artik her ilan ayri satir.
    """
    sid = os.environ["TRENDYOL_SUPPLIER_ID"]
    au = base64.b64encode(("%s:%s" % (os.environ["TRENDYOL_API_KEY"], os.environ["TRENDYOL_API_SECRET"])).encode()).decode()
    h = {"Authorization": "Basic " + au, "User-Agent": sid + " - SelfIntegration"}
    out = []
    for s in range(4):
        r = requests.get("https://apigw.trendyol.com/integration/product/sellers/%s/products" % sid,
                         params={"page": s, "size": 200, "approved": "true"}, headers=h, timeout=90)
        j = r.json()
        for x in j.get("content") or []:
            if x.get("stockCode"):
                out.append((x["stockCode"], x.get("barcode"), x.get("quantity")))
        if s + 1 >= int(j.get("totalPages") or 1):
            break
    return out


def n11():
    import n11_client as c
    out = {}
    for x in c.get("/ms/product-query", page=0, size=200).json().get("content") or []:
        k = str(x.get("stockCode") or "")
        for ek in ("-N11", "-AE"):
            if k.endswith(ek):
                k = k[: -len(ek)]
        out[k] = x.get("quantity")
    return out


def hepsiburada():
    import hepsiburada_client as c
    out = {}
    for off in (0, 100):
        try:
            j = c.get_listings(offset=off, limit=100)
        except Exception as e:
            print("   HB okuma hatasi:", str(e)[:80]); break
        L = j.get("listings") if isinstance(j, dict) else j
        for x in (L or []):
            out[x.get("merchantSku")] = x.get("availableStock")
        if not L:
            break
    return out


def idefix():
    import idefix_client as c
    v = os.environ["IDEFIX_SATICI_ID"]
    tum = json.load(open("C:/Users/serdar/AppData/Local/Temp/claude/C--Users-serdar-Desktop-atolyesocialbotmasaustu/a4d0556e-5012-4f53-831e-17e87b486275/scratchpad/buybox/idx_tum.json", encoding="utf-8"))
    bar = {str(x.get("barcode")): x.get("vendorStockCode") for x in tum}
    out = {}
    try:
        r = c.get("/pim/catalog/%s/products" % v, page=0, size=200)
        for x in (r.json().get("content") or r.json().get("items") or []):
            k = bar.get(str(x.get("barcode"))) or x.get("vendorStockCode")
            if k:
                out[k] = x.get("inventoryQuantity")
    except Exception as e:
        print("   Idefix okuma ucu yok:", str(e)[:80])
    return out


if __name__ == "__main__":
    for ad, fn in (("SHOPIFY", shopify), ("TRENDYOL", trendyol), ("N11", n11),
                   ("HEPSIBURADA", hepsiburada), ("IDEFIX", idefix)):
        try:
            rapor(ad, fn())
        except Exception as e:
            print("!! %-13s HATA %s" % (ad, str(e)[:110]))
