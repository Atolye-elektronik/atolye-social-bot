# -*- coding: utf-8 -*-
"""Kanal fiyatlari + kargo baremi uyum raporu. Cikti: content/fiyat_uyum_raporu.json + ekrana ozet.
Net formulleri (memory: fiyatlama-modeli, pazarama/idefix/pttavm entegrasyon notlari), KDV %20:
  TY : P(1/1.2-0.13) - kargo_ty(P) - 11         kargo_ty: 34.2 (<200) / 65.8 (<400) / 77.5   (KDV haric)
  HB : P(1/1.2-0.13) - kargo_hb(P)/1.2 - 2.5    kargo_hb: 50.4 (<200) / 86.4 (<400) / 94.2 (KDV dahil)
  N11: P(1/1.2-0.17) - kargo_n11(P) - 11        kargo_n11: 96 (<400) / 87.5
  PZ : P(1/1.2-kom) - kargo_pz(P)               kom 0.14 elektronik / 0.17 yapi / 0.18 kirtasiye; kargo 54.58 (<150) / 85.41 (<=300) / 97.98
  PTT: P/1.2*(1-kom_dahil)  (P<250: kargo alici)  - (P>=250: kargo satici ~ 90)
  IDX: P(1/1.2-kom) - 95.46*1.2 (desi 1)        kom 0.10 elektronik / 0.17 yapi / 0.18 kirtasiye
  WEB: P/1.2*0.96  (kargo musteri oder)
"""
import json, os, sys, urllib.request
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def kty(p): return 34.2 if p < 200 else (65.8 if p < 400 else 77.5)
def khb(p): return (50.4 if p < 200 else (86.4 if p < 400 else 94.2)) / 1.2
def kn11(p): return 96.0 if p < 400 else 87.5
def kpz(p): return 54.58 if p < 150 else (85.41 if p <= 300 else 97.98)
GRUP = {"YapiMarket": {"pz": 0.17, "idx": 0.17, "ptt": 0.16}, "Kirtasiye": {"pz": 0.18, "idx": 0.18, "ptt": 0.18}, "Elektronik": {"pz": 0.14, "idx": 0.10, "ptt": 0.15}}
def grup(sk):
    pzf = {x["sk"]: x["g"] for x in json.load(open(os.path.join(KOK, "content", "pazarama_fiyat.json"), encoding="utf-8"))}
    return pzf
def net(kanal, p, g):
    k = GRUP.get(g, GRUP["Elektronik"])
    if kanal == "ty": return p * (1/1.2 - 0.13) - kty(p) - 11
    if kanal == "hb": return p * (1/1.2 - 0.13) - khb(p) - 2.5
    if kanal == "n11": return p * (1/1.2 - 0.17) - kn11(p) - 11
    if kanal == "pz": return p * (1/1.2 - k["pz"]) - kpz(p)
    if kanal == "ptt": return p / 1.2 * (1 - k["ptt"]) - (0 if p < 250 else 90)
    if kanal == "idx": return p * (1/1.2 - k["idx"]) - 95.46 * 1.2
    if kanal == "web": return p / 1.2 * 0.96
def esik_tuzagi(kanal, p):
    """Fiyat, bir kargo esiginin hemen ustundeyse ve esigin altina inmek neti artiriyorsa -> tuzak."""
    esikler = {"ty": [200, 400], "hb": [200, 400], "n11": [400], "pz": [150, 300.01], "ptt": [250]}
    for e in esikler.get(kanal, []):
        if e <= p < e + 60:
            alt = e - 0.01 if kanal != "pz" or e != 300.01 else 300
            if net(kanal, alt, "Elektronik") > net(kanal, p, "Elektronik") + 1:
                return "%s: %.0f TL yerine %.0f TL daha karli (kargo baremi)" % (kanal.upper(), p, alt)
    return None
def main():
    import trendyol_client as tc, hepsiburada_client as hb, n11_client as n11
    from marketplaces import pazarama_client as pz
    F = {}
    def put(sk, kanal, p):
        if sk and p: F.setdefault(sk, {})[kanal] = float(p)
    # WEB
    for pr in json.load(urllib.request.urlopen("https://atolyeelektronik.com/products.json?limit=250"))["products"]:
        for v in pr["variants"]:
            put(v["sku"], "web", v["price"])
    # TY
    for pg in range(6):
        r = tc.get_products_v1(page=pg, size=100); items = r.get("content") or []
        for x in items:
            if x.get("approved") and x.get("onSale") and not x.get("archived"): put(x.get("stockCode"), "ty", x.get("salePrice"))
        if len(items) < 100: break
    # HB
    for off in range(0, 400, 100):
        r = hb.get_listings(offset=off, limit=100); L = r.get("listings") or []
        for x in L:
            if x.get("isSalable"): put(x.get("merchantSku"), "hb", x.get("price"))
        if len(L) < 100: break
    # N11
    for x in n11.get("/ms/product-query", page=0, size=200).json().get("content") or []:
        sk = str(x.get("stockCode") or "")
        for suf in ("-N11", "-AE"):
            if sk.endswith(suf): sk = sk[:-len(suf)]
        if x.get("status") == "Active": put(sk, "n11", x.get("salePrice"))
    # PZ (onayli)
    for pg in range(4):
        d = pz.get("/product/products/approved", Size=100, Page=pg).json().get("data")
        L = (d or {}).get("sellerProducts") if isinstance(d, dict) else (d or [])
        for x in L or []:
            if (x.get("stockCount") or 0) > 0: put(x.get("stockCode"), "pz", x.get("salePrice"))
        if not L or len(L) < 100: break
    # PTT + IDX (gonderilen fiyatlar)
    try:
        import re
        for x in json.load(open(os.path.join(KOK, "content", "pttavm_fiyat_rapor.json"), encoding="utf-8")):
            m = re.search(r"PTT=(\d+)", x.get("not", ""))
            if m: put(x.get("sk"), "ptt", m.group(1))
    except Exception as e: print("ptt raporu okunamadi", e)
    for x in json.load(open(os.path.join(KOK, "content", "idefix_urunler.json"), encoding="utf-8")):
        put(x.get("vendorStockCode"), "idx", x.get("price"))
    # alias (HB/N11 kodlari -> Shopify/TY kodu)
    S = json.load(open(os.path.join(KOK, "content", "shopify_sku.json"), encoding="utf-8"))
    for a, b in (S.get("alias") or {}).items():
        if a in F and b:
            for k, v in F.pop(a).items(): F.setdefault(b, {}).setdefault(k, v)
    G = grup(None)
    rapor = []
    for sk, k in sorted(F.items()):
        if "ty" not in k: continue
        g = G.get(sk, "Elektronik")
        tyn = net("ty", k["ty"], g)
        satir = {"sk": sk, "grup": g, "fiyat": k, "net": {c: round(net(c, p, g), 1) for c, p in k.items()}, "uyari": []}
        for c, p in k.items():
            if c in ("ty", "web"): continue
            if p < k["ty"] - 0.5: satir["uyari"].append("%s fiyati TY'nin altinda (%.0f < %.0f)" % (c.upper(), p, k["ty"]))
            fark = satir["net"][c] - tyn
            if fark < -15: satir["uyari"].append("%s neti TY'den %.0f TL dusuk" % (c.upper(), -fark))
        for c, p in k.items():
            t = esik_tuzagi(c, p)
            if t: satir["uyari"].append(t)
        if "web" in k and k["web"] > k["ty"]: satir["uyari"].append("WEB fiyati TY'den yuksek (%.0f > %.0f)" % (k["web"], k["ty"]))
        rapor.append(satir)
    json.dump(rapor, open(os.path.join(KOK, "content", "fiyat_uyum_raporu.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # ozet
    kanallar = ["web", "ty", "hb", "n11", "pz", "ptt", "idx"]
    print("urun (TY'de satista):", len(rapor))
    print("kanal kapsama:", {c: sum(1 for r in rapor if c in r["fiyat"]) for c in kanallar})
    import statistics as st
    for c in kanallar:
        oran = [r["fiyat"][c] / r["fiyat"]["ty"] for r in rapor if c in r["fiyat"]]
        netf = [r["net"][c] - r["net"]["ty"] for r in rapor if c in r["fiyat"]]
        if oran: print("  %-4s fiyat/TY medyan %.2f  | net-TYnet medyan %+.0f TL (min %+.0f, max %+.0f)" % (c, st.median(oran), st.median(netf), min(netf), max(netf)))
    uy = [r for r in rapor if r["uyari"]]
    print("uyarili urun:", len(uy))
    for r in uy[:60]:
        print("  %-14s TY=%-5.0f %s" % (r["sk"], r["fiyat"]["ty"], " | ".join(r["uyari"])))
if __name__ == "__main__":
    main()
