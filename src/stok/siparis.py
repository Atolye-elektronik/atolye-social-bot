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
from datetime import datetime, timedelta, timezone

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "src"))
sys.path.insert(0, os.path.join(KOK, "src", "marketplaces"))
GORULEN = os.path.join(KOK, "state", "siparis_gorulen.json")
GUNLUK = os.path.join(KOK, "state", "siparis_gunlugu.jsonl")
def _barkod_alias():
    try:
        return json.load(open(os.path.join(KOK, "content", "shopify_sku.json"), encoding="utf-8")).get("barkod_alias", {})
    except FileNotFoundError:
        return {}


BARKOD_ALIAS = _barkod_alias()
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
                        "durum": o.get("status"), "kalemler": _kalemler(o),
                        "tutar": o.get("totalPrice") or o.get("grossAmount"),
                        "musteri": ("%s %s" % (o.get("customerFirstName", ""), o.get("customerLastName", ""))).strip(),
                        "kargo_son": o.get("agreedDeliveryDate") or o.get("estimatedDeliveryEndDate")})
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
            if no in ("None", ""):
                continue  # /packages/unpacked yalniz paket no + barkod verir, siparis degil
            g = grup.setdefault(no, {"no": no, "tarih": _ilk(o, "orderDate", "OrderDate", "createdDate"),
                                     "durum": _ilk(o, "status", "Status", vars=fn.__name__), "kalemler": [],
                                     "tutar": ((o.get("totalPrice") or {}).get("amount") if isinstance(o.get("totalPrice"), dict) else o.get("totalPrice")),
                                     "musteri": _ilk(o, "customerName", "CustomerName", vars=""),
                                     "kargo_son": _ilk(o, "dueDate", "DueDate")})
            kl = _kalemler(o)
            if not kl and _ilk(o, "merchantSKU", "merchantSku"):
                kl = _kalemler({"lines": [o]})
            g["kalemler"].extend(kl)
        out.extend(grup.values())
    # Kargolanmis paketler (HB ayni gun kargolayinca siparis /orders'tan dusuyor): siparis detayindan kalemler
    try:
        r = hb.get_shipped_packages(offset=0, limit=100)
        gorulen = {o["no"] for o in out}
        esik = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        for pk in (r.get("items") or []):
            no = str(pk.get("OrderNumber") or "")
            if not no or no in gorulen or str(pk.get("ShippedDate") or "")[:10] < esik:
                continue
            try:
                d = hb.get_order_detail(no)
            except Exception as e:
                print("  HB detay", no, str(e)[:80]); continue
            kl = [{"kod": it.get("merchantSKU") or it.get("merchantSku"), "barkod": it.get("productBarcode"),
                   "adet": int(it.get("quantity") or 1)} for it in (d.get("items") or []) if str(it.get("status", "")).lower() not in IPTAL]
            tutar = sum(float(((it.get("totalPrice") or {}).get("amount") or 0)) for it in (d.get("items") or []))
            out.append({"no": no, "tarih": d.get("orderDate"), "durum": "Shipped", "kalemler": kl, "tutar": tutar,
                        "musteri": (d.get("customer") or {}).get("name", ""), "kargo_son": str(pk.get("ShippedDate") or "")[:16]})
            gorulen.add(no)
    except Exception as e:
        print("  HB shipped hata:", str(e)[:120])
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


def topla_shopify(gun=14):
    """Web (Shopify) siparisleri — Admin GraphQL, SHOPIFY_ADMIN_TOKEN gerekir (read_orders).
    Shopify satilan SKU'nun stogunu kendisi duser; burada amac SET satisini PARCALARA acmak.
    Bu yuzden satis_dus'ta set SKU'sunun kendi dusumu degil, parca dusumu esas alinir."""
    from stok import shopify_admin as sa
    out = []
    q = """query($q:String,$after:String){ orders(first:50, query:$q, after:$after, sortKey:CREATED_AT, reverse:true){
      pageInfo{hasNextPage endCursor}
      nodes{ name createdAt cancelledAt displayFulfillmentStatus totalPriceSet{ shopMoney{ amount } }
             lineItems(first:30){ nodes{ sku quantity variant{ barcode } } } } } }"""
    bas = (datetime.now() - timedelta(days=gun)).strftime("%Y-%m-%d")
    after = None
    while True:
        d = sa.gql(q, {"q": "created_at:>=%s" % bas, "after": after})["orders"]
        for o in d["nodes"]:
            if o.get("cancelledAt"):
                continue
            kl = [{"kod": li["sku"], "barkod": (li.get("variant") or {}).get("barcode"), "adet": int(li["quantity"])}
                  for li in o["lineItems"]["nodes"] if li.get("sku")]
            out.append({"no": o["name"], "tarih": o["createdAt"], "durum": o.get("displayFulfillmentStatus"), "kalemler": kl,
                        "tutar": ((o.get("totalPriceSet") or {}).get("shopMoney") or {}).get("amount")})
        if not d["pageInfo"]["hasNextPage"]:
            break
        after = d["pageInfo"]["endCursor"]
    return out


def topla_amazon(gun=14):
    """Amazon SP-API Orders v0. Alici bilgisi (PII) gelmez; kalemler orderItems ile."""
    from marketplaces import amazon_client as az
    out = []
    bas = (datetime.now(timezone.utc) - timedelta(days=gun)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for o in az.orders(bas):
        no = o["AmazonOrderId"]
        durum = o.get("OrderStatus")
        kl = []
        if durum not in ("Canceled", "Pending"):
            kl = [{"kod": it.get("SellerSKU"), "barkod": None, "adet": int(it.get("QuantityOrdered") or 0)}
                  for it in az.order_items(no) if it.get("SellerSKU") and int(it.get("QuantityOrdered") or 0) > 0]
        out.append({"no": no, "tarih": o.get("PurchaseDate"), "durum": durum, "kalemler": kl,
                    "tutar": (o.get("OrderTotal") or {}).get("Amount"), "musteri": "",
                    "kargo_son": o.get("LatestShipDate")})
    return out


TOPLAYICI = {"shopify": topla_shopify, "trendyol": topla_trendyol, "hepsiburada": topla_hepsiburada, "n11": topla_n11,
             "pazarama": topla_pazarama, "idefix": topla_idefix, "amazon": topla_amazon}
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


def _zaman(t):
    """Tarih alanini datetime'a cevirir (ms epoch / ISO / 'YYYY-MM-DD HH:MM'); yerel saat."""
    if isinstance(t, (int, float)):
        return datetime.fromtimestamp(t / 1000)
    s = str(t or "")[:16].replace("T", " ")
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None


def liste(kanallar, dosya, sadece_bugun=False):
    """Stoktan bagimsiz siparis listesi: tum kanallar, son 14 gun (veya sadece bugun), Excel."""
    import openpyxl
    from openpyxl.styles import Font
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Siparisler"
    ws.append(["Kanal", "Siparis no", "Tarih", "Durum", "Musteri", "Tutar", "Kargo son", "Urunler"])
    for c in ws[1]: c.font = Font(bold=True)
    say = {}
    for k in kanallar:
        try:
            L = TOPLAYICI[k]()
        except Exception as e:
            print("  %s hata: %s" % (k, str(e)[:120])); continue
        if sadece_bugun:
            # Kesit: dun 14:00 < siparis <= bugun 14:00 (kullanici 07.09). 14:00'ten sonra calisirsa
            # bugun 14:00 -> yarin 14:00 degil, yine "son 14:00"e kadar olan pencere alinir.
            simdi = datetime.now()
            son = simdi.replace(hour=14, minute=0, second=0, microsecond=0)
            if simdi < son:
                son -= timedelta(days=1)
            bas = son - timedelta(days=1)
            L = [o for o in L if (_zaman(o.get("tarih")) or bas) > bas and (_zaman(o.get("tarih")) or son) <= son]
            print("kesit: %s -> %s" % (bas.strftime("%d.%m %H:%M"), son.strftime("%d.%m %H:%M")))
        say[k] = len(L)
        for o in L:
            t = o.get("tarih")
            if isinstance(t, (int, float)):
                t = datetime.fromtimestamp(t / 1000).strftime("%Y-%m-%d %H:%M")
            ks = o.get("kargo_son")
            if isinstance(ks, (int, float)):
                ks = datetime.fromtimestamp(ks / 1000).strftime("%Y-%m-%d")
            urun = ", ".join("%s x%d" % (kl.get("kod") or kl.get("barkod"), kl["adet"]) for kl in o["kalemler"])
            ws.append([k, o["no"], str(t or "")[:16], o.get("durum"), o.get("musteri", ""), o.get("tutar"), str(ks or "")[:10], urun])
    ws.freeze_panes = "A2"
    for col, w in zip("ABCDEFGH", [12, 18, 17, 14, 22, 10, 12, 70]):
        ws.column_dimensions[col].width = w
    wb.save(dosya)
    print("kanal basina siparis:", say, "->", dosya)
    for r in ws.iter_rows(min_row=2, values_only=True):
        print("  %-11s %-14s %-16s %-10s %8s  %s" % (r[0], str(r[1])[:14], r[2], str(r[3])[:10], r[5] if r[5] is not None else "", r[7][:60]))
    return say


def main():
    a = sys.argv[1:]
    if "--liste" in a:
        kanallar = [a[a.index("--kanal") + 1]] if "--kanal" in a else list(TOPLAYICI)
        bugun = "--bugun" in a
        varsayilan = "SIPARIS-BUGUN.xlsx" if bugun else "SIPARISLER.xlsx"
        dosya = a[a.index("--liste") + 1] if len(a) > a.index("--liste") + 1 and a[a.index("--liste") + 1].endswith(".xlsx") else os.path.join(os.path.expanduser("~"), "Desktop", varsayilan)
        liste(kanallar, dosya, sadece_bugun=bugun); return
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
            # Barkod alias once: TY bazi urunlere yanlis stockCode veriyor (orn. Mini Duy 2920000600056 -> "AEDUYAMP-1")
            kod = BARKOD_ALIAS.get(str(kl.get("barkod"))) or kl["kod"] or bh.get(str(kl["barkod"]))
            if not kod:
                print("  ! %s %s: kod cozulemedi %s" % (o["kanal"], o["no"], kl))
                continue
            sh = R.kanonik(kod)
            if sh not in parca and sh not in R.setler:
                print("  ! %s %s: '%s' Shopify'da/recetede yok (alias ekle: content/shopify_sku.json)" % (o["kanal"], o["no"], kod))
                gunluk({"an": datetime.now().isoformat(timespec="minutes"), "kanal": o["kanal"], "no": o["no"],
                        "kod": kod, "adet": kl["adet"], "hata": "bilinmeyen kod", "kuru": kuru})
                continue
            if o["kanal"] == "shopify" and sh not in R.setler:
                # Web'de satilan tekil parcanin stogunu Shopify zaten dusuyor; cift dusum yapma.
                print("  %-12s %-14s %-14s x%d -> Shopify kendi dustu (parca)" % (o["kanal"], o["no"], sh, kl["adet"]))
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
    # GUVENLIK: kanallara stok dagitimi ancak parca sayimi Shopify'a girildikten sonra (STOK_DAGIT=1).
    # Aksi halde sayilmamis (0 gorunen) parcalar tum setleri kanallarda 0'a cekerdi.
    if os.environ.get("STOK_DAGIT") == "1":
        kanallar = os.environ.get("STOK_KANALLAR", "trendyol,hepsiburada,n11,pazarama,idefix").split(",")
        print(merkez.dagit(hedef, kanallar, kuru=False))
    else:
        print("(STOK_DAGIT=1 degil: kanallara stok yazilmadi, yalniz Shopify dusumu yapildi)")
    gorulen_yaz(g)


if __name__ == "__main__":
    main()
