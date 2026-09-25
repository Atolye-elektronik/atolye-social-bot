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
    """{kanal_stok_kodu: adet} — Shopify SKU'sunu kanal kodlarina acar (alias tersi + kendisi).

    25.09.2026 DUZELTME: negatif hedef (oversell/kayip senkron nedeniyle) hicbir
    yerde 0'a sabitlenmiyordu; -1 gibi bir deger pazaryerine OLDUGU GIBI
    gonderiliyordu (AEACDMMR -1 -> HB yeni siparis almaya devam etti). Kanala
    cikan her deger artik en az 0.
    """
    ters = _alias_ters()
    out = {}
    for sku, adet in hedef.items():
        if adet is None:
            continue
        adet = max(0, adet)
        for kod in [sku] + ters.get(sku, []):
            out[kod] = adet
    return out


SNAPSHOT = os.path.join(KOK, "state", "ty_katalog_snapshot.json")


def barkod_duzeltme():
    """Trendyol'da stok kodu YANLIS urunu gosteren ilanlar: barkod -> gercek kod.

    13.09.2026: TYBW805DFS3U8DIC36 barkodlu "2 Pin Siyah Anahtar Switch Mini
    Buton" ilaninin merchantSku'su AEBZZR5V (buzzer) gorunuyor. Uc ayda 18 adet
    switch satildi ve her seferinde BUZZER stogu dustu. merchantSku sonradan
    degistirilemedigi icin duzeltmeyi barkod duzeyinde yapiyoruz.
    """
    try:
        d = json.load(open(os.path.join(KOK, "content", "barkod_duzeltme.json"), encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return {k: v for k, v in d.items() if not k.startswith("_")}


def ty_katalog_yenile():
    """Trendyol katalogunu canli ceker ve snapshot'i tazeler.

    13.09.2026: snapshot tek seferlik uretilmis ve bayatlamisti (119 kayit).
    Sonradan acilan urunlerin barkodu icinde olmadigi icin stok guncellemesi
    onlara HIC gitmiyordu - sessizce atlaniyorlardi. Artik her dagitimda
    tazeleniyor; ag/kimlik hatasinda eski dosyaya dusuluyor.
    """
    import base64
    import requests
    sid = os.environ["TRENDYOL_SUPPLIER_ID"]
    au = base64.b64encode(("%s:%s" % (os.environ["TRENDYOL_API_KEY"],
                                      os.environ["TRENDYOL_API_SECRET"])).encode()).decode()
    h = {"Authorization": "Basic " + au, "User-Agent": "%s - SelfIntegration" % sid}
    tum, sayfa = [], 0
    while True:
        r = requests.get("https://apigw.trendyol.com/integration/product/sellers/%s/products" % sid,
                         params={"page": sayfa, "size": 200, "approved": "true"}, headers=h, timeout=90)
        r.raise_for_status()
        j = r.json()
        tum.extend(j.get("content") or [])
        sayfa += 1
        if sayfa >= int(j.get("totalPages") or 1):
            break
    kayit = [{"stockCode": x.get("stockCode"), "barcode": x.get("barcode"),
              "quantity": x.get("quantity"), "title": x.get("title")} for x in tum if x.get("stockCode")]
    json.dump(kayit, open(SNAPSHOT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return kayit


def _barkodlar():
    """kanal stok kodu -> {ty: TY barkodu, ean: 13 haneli}"""
    b = {}
    try:
        kayit = ty_katalog_yenile()
    except Exception as e:
        print("! TY katalogu tazelenemedi (%s), snapshot kullaniliyor" % str(e)[:90])
        try:
            kayit = json.load(open(SNAPSHOT, encoding="utf-8"))
        except FileNotFoundError:
            kayit = []
    # 13.09.2026 BUG: setdefault yalnizca ILK barkodu tutuyordu. Trendyol'da
    # 6 stok kodunun 2-3 AKTIF ilani var (mukerrer ilanlar); stok yalnizca bir
    # ilana gidiyor, digerleri aylardir eski sayida kaliyordu - kullanici
    # uygulamada AEVHM314'u 40 ve 30 olarak yan yana gordu. Artik TUM barkodlar.
    duz = barkod_duzeltme()
    # 19.09.2026: mukerrer ilanlar kapatildi (stok 0). Kapali barkodlara stok basilirsa
    # ilan yeniden acilir; bu yuzden content/ty_kapali_barkod.json'dakiler atlanir.
    try:
        kapali = set(k for k in json.load(open(os.path.join(KOK, "content", "ty_kapali_barkod.json"), encoding="utf-8")) if not k.startswith("_"))
    except FileNotFoundError:
        kapali = set()
    for u in kayit:
        sk = duz.get(u.get("barcode")) or u.get("stockCode")
        if not sk or not u.get("barcode") or u.get("barcode") in kapali:
            continue
        d = b.setdefault(sk, {})
        d.setdefault("ty", u["barcode"])              # geriye donuk uyum
        d.setdefault("ty_hepsi", [])
        if u["barcode"] not in d["ty_hepsi"]:
            d["ty_hepsi"].append(u["barcode"])
    for u in json.load(open(os.path.join(KOK, "content", "n11_urunler.json"), encoding="utf-8")):
        sk = u.get("tyStokKodu") or u["stokKodu"]
        b.setdefault(sk, {})["ean"] = str(u.get("barkod") or "")
    return b


# ---------------- Trendyol: barkod + quantity ----------------
def stok_bas_trendyol(hedef, kuru=True):
    import trendyol_client as tc
    bk = _barkodlar()
    items = [{"barcode": bar, "quantity": int(v)}
             for k, v in _kanal_kodlari(hedef).items()
             if k in bk
             for bar in (bk[k].get("ty_hepsi") or ([bk[k]["ty"]] if bk[k].get("ty") else []))]
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
def _n11_kodlari():
    """bizim stok kodu -> N11'deki GERCEK stockCode.

    13.09.2026 BUG: N11'de kodlarin sonunda -N11 / -AE eki var. Duz kodu
    gonderince N11 istegi 200 ile kabul ediyor ama HICBIR urunu guncellemiyordu;
    118 urun aylardir eski stokla duruyordu. Artik gercek kodla gonderiliyor.
    """
    import n11_client as n11
    d = n11.get("/ms/product-query", page=0, size=200).json().get("content") or []
    out = {}
    for x in d:
        tam = str(x.get("stockCode") or "")
        sade = tam
        for ek in ("-N11", "-AE"):
            if sade.endswith(ek):
                sade = sade[: -len(ek)]
        if sade:
            out[sade] = tam
    return out


def stok_bas_n11(hedef, kuru=True):
    import n11_client as n11
    kod = _n11_kodlari()
    istek = _kanal_kodlari(hedef)
    items = [{"stockCode": kod[k], "quantity": int(v)} for k, v in istek.items() if k in kod]
    if kuru:
        return "kuru: %d stok kodu (%d kod N11'de yok)" % (len(items), len(istek) - len(items))
    sonuc = []
    for i in range(0, len(items), 100):
        sonuc.append(n11.post("/ms/product/tasks/price-stock-update",
                              {"payload": {"integrator": n11.ENTEGRATOR, "skus": items[i:i + 100]}}).status_code)
    return "N11: %d urun, partiler %s" % (len(items), sonuc)


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
    """stokKodu -> [Pazarama code, ...]. state/pazarama_katalog.json'dan; yoksa API'den ceker.

    13.09.2026 DUZELTME: eskiden stok kodu basina TEK code tutuluyordu. Pazarama'da
    3 stok kodunun 2 ilani var (AEBZZR5V, AERC522RFID, AEVHM314); ikincilere stok
    hic gitmiyordu. AEBZZR5V'nin ikinci ilani ("2 Pin Siyah Anahtar Switch") bu
    yuzden 0 stokla satisa kapanmis, duzenleme ekrani bile devre disi kalmisti.
    Ayrica content/barkod_duzeltme.json burada da uygulanir: o ilan aslinda
    switch, stogu AEDC125B'den gelmeli.
    """
    from marketplaces import pazarama_client as pc
    yol = os.path.join(KOK, "state", "pazarama_katalog.json")
    try:
        d = json.load(open(yol, encoding="utf-8"))
        if d and all(isinstance(v, list) for v in d.values()):
            return d
    except FileNotFoundError:
        pass
    duz = barkod_duzeltme()
    g = {}
    for y in ("/product/products/approved", "/product/products/unapproved"):
        for p in range(8):
            d = pc.get(y, Size=100, Page=p).json().get("data")
            l = (d or {}).get("sellerProducts") if isinstance(d, dict) else (d or [])
            l = l or []
            yeni = 0
            for x in l:
                if not x.get("stockCode") or not x.get("code"):
                    continue
                sk = duz.get(x["code"]) or x["stockCode"]
                liste = g.setdefault(sk, [])
                if x["code"] not in liste:
                    liste.append(x["code"]); yeni += 1
            if yeni == 0 or len(l) < 100:
                break
    json.dump(g, open(yol, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return g


def stok_bas_pazarama(hedef, kuru=True):
    from marketplaces import pazarama_client as pc
    bk = _pazarama_barkodlari()
    items = [{"code": c, "stockCount": int(v)}
             for k, v in _kanal_kodlari(hedef).items() if k in bk
             for c in bk[k]]
    if kuru:
        return "kuru: %d barkod" % len(items)
    r = pc.post("/product/updateStock-v2", {"items": items})
    return r.status_code, r.text[:300]


# ---------------- Amazon: AEMZN-<kod> + fulfillment_availability ----------------
def stok_bas_amazon(hedef, kuru=True):
    """Amazon SP-API listing patch ile stok yazar.

    13.09.2026 EKLENDI: siparis toplayicida amazon vardi ama stok BASILMIYORDU -
    Amazon'dan satis gelince parca stogu dususe girip diger kanallar guncelleniyor,
    Amazon ilaninin kendi stogu ise oldugu gibi kaliyordu.
    SKU kalibi: AEMZN-<bizim kod>. productType her ilandan okunur (urune gore degisiyor,
    sabit bir deger patch'i reddettiriyor).
    """
    import time
    from marketplaces import amazon_client as az
    try:
        teklif = json.load(open(os.path.join(KOK, "content", "amazon_teklif.json"), encoding="utf-8"))
    except FileNotFoundError:
        return "amazon_teklif.json yok"
    kodlar = _kanal_kodlari(hedef)
    hedefler = [(x["sku"], kodlar[x["sku"]]) for x in teklif if x.get("sku") in kodlar]
    if kuru:
        return "kuru: %d ilan" % len(hedefler)
    ok, hata = 0, []
    for kod, adet in hedefler:
        sku = "AEMZN-" + kod
        try:
            r = az.listing(sku)
            if r.status_code != 200:
                hata.append("%s okunamadi %s" % (kod, r.status_code)); continue
            pt = (r.json().get("summaries") or [{}])[0].get("productType")
            rr = az.stok_yaz(sku, int(adet), product_type=pt)
            j = rr.json() if hasattr(rr, "json") else {}
            err = [i for i in (j.get("issues") or []) if i.get("severity") == "ERROR"]
            if err:
                hata.append("%s %s" % (kod, str(err)[:70]))
            else:
                ok += 1
        except Exception as e:
            hata.append("%s %s" % (kod, str(e)[:70]))
        time.sleep(0.6)
    return "Amazon: %d ilan yazildi%s" % (ok, (" | hata: " + "; ".join(hata[:4])) if hata else "")
