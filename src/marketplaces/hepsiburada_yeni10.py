# -*- coding: utf-8 -*-
"""Shopify-only 10 urunu Hepsiburada'ya acar (05.09.2026). Kaynak content/n11_yeni_10.json + TY fiyati.
HB fiyati: TY ile esit-net hesabinda (kom %13, kargo 50,40/86,40/94,20 KDV dahil, hizmet 2,5) TY'nin altina
dustugu icin taban = TY fiyati. Kullanim (src/marketplaces icinde): python hepsiburada_yeni10.py [--gonder]
"""
import json, os, sys
import hepsiburada_catalog as katalog
from hepsiburada_urun_ekle import temiz_aciklama, ad_kisalt, gonderilmisler, durum_kaydet, MARKA, KDV_ORANI, GARANTI_AY

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KAT = {
    "AE5X100DT": (13003168, {"turu": "Düz Tornavida"}),
    "AE5X100YT": (13003168, {"turu": "Yıldız Tornavida"}),
    "AEKNTKLM": (60006732, {}),
    "AES400IGG": (60002016, {}),          # Hirdavat > Is Guvenlik > Gozluk
    "AE5IZOLE": (13003359, {}),           # Hirdavat > Yapistirici ve Bantlar
    "AEMYNK": (13003157, {}),             # Yan Keski
    "AEDUY-1": (23024292, {"yas_araligi": "8+ Yaş"}),
    "AEAMP-1": (23024292, {"yas_araligi": "8+ Yaş"}),
    "AEPY18650T": (23024292, {"yas_araligi": "8+ Yaş"}),
    "AE9VPILSKT1": (23024292, {"yas_araligi": "8+ Yaş"}),
}


def payloadlar():
    ty = json.load(open(os.path.join(KOK, "content", "trendyol_yeni_10.json"), encoding="utf-8"))
    fiyat = {u["stokKodu"]: u["fiyat"] for u in ty["urunler"] + ty["beklemede"]}
    out = []
    for u in json.load(open(os.path.join(KOK, "content", "n11_yeni_10.json"), encoding="utf-8")):
        sk = u["stokKodu"].replace("-N11", "")
        cid, ek = KAT[sk]
        ad, _ = ad_kisalt(u["ad"])
        g = u["gorseller"][:5]
        oz = {"merchantSku": sk, "Barcode": str(u["barkod"]), "UrunAdi": ad,
              "UrunAciklamasi": temiz_aciklama(u["aciklama"]), "Marka": MARKA,
              "GarantiSuresi": int(GARANTI_AY), "kg": 1, "tax_vat_rate": KDV_ORANI,
              "00000MU": g[0], "price": str(fiyat[sk]), "stock": str(u["stok"])}
        for i, s in enumerate(g, start=1):
            oz["Image%d" % i] = s
        oz.update(ek)
        out.append({"categoryId": cid, "merchant": katalog.MERCHANT_ID, "attributes": oz})
    return out


def main():
    # turu degerlerini dogrula
    vals = {v["value"] for v in katalog.get_attribute_values(13003168, "turu")}
    for k in ("Düz Tornavida", "Yıldız Tornavida"):
        print("turu", k, "->", k in vals)
    P = payloadlar()
    for p in P:
        a = p["attributes"]; print("  %-12s kat=%s fiyat=%s stok=%s %s" % (a["merchantSku"], p["categoryId"], a["price"], a["stock"], a["UrunAdi"][:50]))
    if "--gonder" not in sys.argv:
        print("(kuru)"); return
    sonuc = katalog.create_products(P, multipart=True)
    print("HB:", json.dumps(sonuc, ensure_ascii=False)[:800])
    tr = (sonuc.get("data") or {}).get("trackingId") or sonuc.get("trackingId")
    kayit = gonderilmisler()
    for p in P:
        kayit[p["attributes"]["merchantSku"]] = {"barkod": p["attributes"]["Barcode"], "trackingId": tr}
    durum_kaydet(kayit)
    print("trackingId:", tr)


if __name__ == "__main__":
    main()
