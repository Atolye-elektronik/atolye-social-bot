# -*- coding: utf-8 -*-
"""Idefix'e urun ekleme (merchantapi, X-API-KEY).

Fiyat: Trendyol ile esit net kar, taban TY fiyati.
  TY_net = P_ty*(1/1.2 - 0.13) - kargo_ty(P_ty) - 11
  P_idx  = ceil( (TY_net + kargo_idx(desi)) / (1/1.2 - komisyon) )
Komisyon KDV DAHIL (panel > Ticari Kosullar). Kargo: Idefix anlasmali Surat listesi
(KDV haric, x1.20), teslim edilen her siparis satici hesabindan dusulur.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from marketplaces import idefix_client as ix                      # noqa: E402
from marketplaces.pazarama_urun_ekle import katalog, _duz_metin  # noqa: E402

KDV = 1.20
KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Idefix yaprak kategori id -> komisyon (KDV dahil)
KAT = {
    "gelistirme": (230593708, 0.10),   # Elektronik Malzemeler > ... > Gelistirme Kartlari
    "deneysel":   (230553881, 0.10),   # ... > Devre Prototipi Olusturma > Deneysel Devreler (setler)
    "aksesuar":   (230591683, 0.10),   # ... > Devre Karti Aksesuarlari (modul, sensor, kablo)
    "direnc":     (230549217, 0.10),
    "pense":      (530391424, 0.17),
    "yankeski":   (530326233, 0.17),
    "kargaburun": (530397574, 0.17),
    "lehim":      (530367678, 0.17),
    "takimcanta": (530354996, 0.17),
    "multimetre": (530315234, 0.17),
    "voltajded":  (530337017, 0.17),
    "kareli":     (330510077, 0.18),   # Kirtasiye > Okul Defteri > Kareli Defter
    "cizgili":    (330546711, 0.18),
}
OZEL = {
    "AELHMPMP": "lehim", "AEHVYSHP": "lehim", "AEZD30C40W": "lehim", "AEHVYST6P": "lehim",
    "AEMYNK3": "yankeski", "AEYNKSK160": "yankeski",
    "AEPNS180": "pense", "AEEAS3P": "pense", "AEEAS7P": "takimcanta",
    "AEKB1602": "kargaburun",
    "AEDT830D": "multimetre", "AEUT12D": "voltajded",
    "AETC162": "takimcanta", "AEPLSTKKT": "takimcanta", "AETCS9P": "takimcanta", "AETCS18P": "takimcanta",
    "AETEMDEF": "kareli", "AETMRNDFTR10": "kareli", "AETMRNDFTR20": "kareli", "AETMRNDFTR30": "kareli",
    "AESTJDFTR": "cizgili", "AEISDSYS10": "cizgili", "AEISDSYS20": "cizgili",
    "AEUNOR3": "gelistirme", "AEUNOR32": "gelistirme", "AEUNOR33": "gelistirme",
    "AEARNANOTC": "gelistirme", "AEARNANOTC2": "gelistirme",
    "AEPOT10K": "direnc", "AEPOT10K-6": "direnc",
    # 05.09 Shopify-only tekil urunler
    "AE5X100DT": "tornavida", "AE5X100YT": "tornavida", "AEKNTKLM": "kontrolkal",
    "AE5IZOLE": "yalitimbant", "AEMYNK": "yankeski", "AES400IGG": "gozluk",
    "AEDUY-1": "aksesuar", "AEAMP-1": "aksesuar", "AEPY18650T": "aksesuar", "AE9VPILSKT1": "aksesuar",
}
KAT.update({
    "tornavida":   (530371553, 0.17),   # Yapi Market > Manuel El Aletleri > Tornavida
    "kontrolkal":  (530311903, 0.17),
    "gozluk":      (530353566, 0.17),   # Is Guvenlik Urunleri > Maske & Siperlik & Filtre (Idefix'te gozluk yapragi yok)
    "yalitimbant": (530342479, 0.17),   # Yapi Market > Hirdavat > Yapistirici ve Bantlar
})
# Shopify-only urunlerin TY katalogunda olmayanlari icin kaynak: content/trendyol_yeni_10.json
EK_KAYNAK = [os.path.join(KOK, "content", "trendyol_yeni_10.json"), os.path.join(KOK, "content", "trendyol_yeni_2.json")]
SET_IPUCU = ("SET", "ROBOT", "RAK", "RBT", "ELK", "SES", "SNST", "PS")

# Surat Kargo, KDV haric (28.01.2026 listesi): desi ust siniri -> ucret
SURAT = [(1, 95.46), (2, 98.29), (3, 109.82), (4, 117.71), (5, 125.14), (6, 136.64), (7, 145.89),
         (8, 155.11), (9, 164.34), (10, 173.57), (11, 179.37), (12, 186.90), (13, 194.40),
         (14, 201.91), (15, 209.34), (16, 221.06), (17, 232.74), (18, 244.48), (19, 256.19), (20, 267.88)]


def kargo_ty(t):
    return 34.2 if t < 200 else (65.8 if t < 400 else 77.5)


def kargo_idx(desi):
    for ust, uc in SURAT:
        if desi <= ust:
            return uc * KDV
    return 267.88 * KDV


def fiyat(p_ty, kom, desi):
    ty_net = p_ty * (1 / KDV - 0.13) - kargo_ty(p_ty) - 11
    p = math.ceil((ty_net + kargo_idx(desi)) / (1 / KDV - kom))
    return max(p, math.ceil(p_ty))


def kategori(sk):
    if sk in OZEL:
        return OZEL[sk]
    u = sk.upper()
    if any(ip in u for ip in SET_IPUCU):
        return "deneysel"
    return "aksesuar"


def urunler(brand_id, ship_id, ret_id, vat=20):
    n11 = {(u.get("tyStokKodu") or u["stokKodu"]): u for u in json.load(
        open(os.path.join(KOK, "content", "n11_urunler.json"), encoding="utf-8"))}
    kat = {u.get("stockCode"): u for u in katalog()}
    # TY'ye yeni eklenen (henuz onaysiz) urunler: yerel dosyadan tamamla
    for yol in EK_KAYNAK:
        try:
            for u in json.load(open(yol, encoding="utf-8"))["urunler"]:
                kat.setdefault(u["stokKodu"], {"stockCode": u["stokKodu"], "title": u["ad"], "description": u["aciklama"],
                                                "salePrice": u["fiyat"], "quantity": u["stok"], "barcode": u["barkod"],
                                                "images": [{"url": g} for g in u["gorseller"]]})
        except FileNotFoundError:
            pass
    pz = {x["sk"] for x in json.load(open(os.path.join(KOK, "content", "pazarama_fiyat.json"), encoding="utf-8"))}
    hedef = sorted(pz | {"AEPYAA2", "AEPY18650", "AEPY18650T5", "AEPY18650T10", "AEEAS7P"}
                   | {"AE5X100DT", "AE5X100YT", "AEKNTKLM", "AEMYNK", "AEDUY-1", "AEAMP-1", "AEPY18650T", "AE9VPILSKT1", "AES400IGG", "AE5IZOLE"})
    cikti, rapor = [], []
    for sk in hedef:
        u = kat.get(sk)
        if not u or not u.get("salePrice"):
            rapor.append((sk, "TY yok")); continue
        anah = kategori(sk)
        cid, kom = KAT[anah]
        desi = float((n11.get(sk) or {}).get("desi") or 1)
        p_ty = float(u["salePrice"])
        p = fiyat(p_ty, kom, desi)
        bar = str((n11.get(sk) or {}).get("barkod") or u.get("barcode"))
        cikti.append({
            "barcode": bar, "title": u["title"][:150], "productMainId": sk,
            "brandId": brand_id, "categoryId": cid,
            "inventoryQuantity": int(u.get("quantity") or 10), "vendorStockCode": sk,
            "description": _duz_metin(u.get("description") or "") or u["title"],
            "price": p, "vatRate": vat, "desi": desi,
            "deliveryType": "same_day_shipping", "deliveryDuration": 1,
            "shipmentAddressId": ship_id, "returnAddressId": ret_id,
            "images": [{"url": im["url"]} for im in u.get("images", [])[:8]],
            "attributes": [],
        })
        rapor.append((sk, "%-10s kom=%.0f%% desi=%g TY=%.0f -> IDX=%d" % (anah, kom * 100, desi, p_ty, p)))
    return cikti, rapor


def main():
    brand = int(os.environ.get("IDEFIX_BRAND_ID") or 0)
    ship = int(os.environ.get("IDEFIX_SHIP_ADDR") or 79357)
    ret = int(os.environ.get("IDEFIX_RET_ADDR") or 79356)
    cikti, rapor = urunler(brand, ship, ret)
    json.dump(cikti, open(os.path.join(KOK, "content", "idefix_urunler.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for sk, n in rapor:
        print("  %-14s %s" % (sk, n))
    print("hazir urun:", len(cikti), "| brandId:", brand)
    if "--gonder" in sys.argv:
        if not brand:
            print("IDEFIX_BRAND_ID yok, gonderilmedi")
            return
        vendor = os.environ["IDEFIX_SATICI_ID"]
        i = sys.argv.index("--gonder")
        adet = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else len(cikti)
        r = ix.post("/pim/pool/%s/create" % vendor, {"products": cikti[:adet]})
        print("create ->", r.status_code, r.text[:600])


if __name__ == "__main__":
    main()
