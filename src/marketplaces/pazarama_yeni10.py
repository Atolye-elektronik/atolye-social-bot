# -*- coding: utf-8 -*-
"""Shopify-only 10 urunu Pazarama'ya ekler (05.09.2026).

Kaynak: content/n11_yeni_10.json (ad/aciklama/gorsel/barkod, stok kodu -N11 eki atilir)
        content/trendyol_yeni_10.json (TY fiyati; beklemede olanlar dahil)
Fiyat: TY ile esit net (memory: pazarama-entegrasyonu), Surat ayni gun baremi, KDV haric.
Kullanim (src dizininden):  python -m marketplaces.pazarama_yeni10 [--tek KOD] [--hepsi] [--sonuc ID]
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from marketplaces import pazarama_client as pz          # noqa: E402
from marketplaces.pazarama_urun_ekle import _duz_metin, marka_id, _hatalari_ayikla, sonuc  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OZL = json.load(open(os.path.join(KOK, "state", "pazarama_kategori_ozellik.json"), encoding="utf-8"))

KAT = {  # anahtar -> (kategori GUID, komisyon KDV haric)
    "tornavida": ("2997cdc1-84de-40a3-963f-20217f03f7de", 0.17),
    "kontrolkal": ("4d8bdc5a-164c-4457-ae5a-0f107d2183de", 0.17),
    "gozluk": ("7cb0d978-d8d3-4b1b-aa1c-9acb2409fd88", 0.17),
    "bant": ("33fcfd6f-475e-4a13-a2ec-6482e9fcd0c4", 0.18),
    "yankeski": ("700bd912-f103-4288-adc5-f5c276bea981", 0.17),
    "arduino": ("5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9", 0.14),
}
URUN = {  # stok kodu -> (kategori, {ozellik adi: deger adi})
    "AE5X100DT": ("tornavida", {"Renk": "Siyah", "Tornavida Sayısı": "1"}),
    "AE5X100YT": ("tornavida", {"Renk": "Siyah", "Tornavida Sayısı": "1"}),
    "AEKNTKLM": ("kontrolkal", {"Renk": "Sarı", "Led Gösterge": "Var", "Uç Tipi": "Düz"}),
    "AES400IGG": ("gozluk", {"Renk": "Şeffaf", "Ayarlanabilirlik": "Var", "Ürün Tipi": "Çapak Gözlüğü"}),
    "AE5IZOLE": ("bant", {"Bant Adet Sayısı": "Çoklu", "Ürün Türü": "Bant"}),
    "AEMYNK": ("yankeski", {"Renk": "Siyah", "Ürün Tipi": "Mikro Yan Keski", "Uzunluk": "110 mm"}),
    "AEDUY-1": ("arduino", {}), "AEAMP-1": ("arduino", {}),
    "AEPY18650T": ("arduino", {}), "AE9VPILSKT1": ("arduino", {}),
}


def kargo_ty(t):
    return 34.2 if t < 200 else (65.8 if t < 400 else 77.5)


def kargo_pz(p):
    return 54.58 if p < 150 else (85.41 if p <= 300 else 97.98)


def fiyat(p_ty, kom):
    ty_net = p_ty * (1 / 1.2 - 0.13) - kargo_ty(p_ty) - 11
    adaylar = []
    for k in (54.58, 85.41, 97.98):
        p = math.ceil((ty_net + k) / (1 / 1.2 - kom))
        if kargo_pz(p) == k:
            adaylar.append(p)
    p = min(adaylar) if adaylar else math.ceil((ty_net + 85.41) / (1 / 1.2 - kom))
    return max(p, math.ceil(p_ty))


def ozellikler(anah, secim):
    d = OZL[KAT[anah][0]]
    out, eksik = [], []
    for a in d.get("attributes") or []:
        ad = a["name"]
        vals = a.get("attributeValues") or a.get("values") or []
        istenen = secim.get(ad)
        if istenen is None:
            if a.get("isRequired"):
                eksik.append(ad)
            continue
        v = next((v for v in vals if (v.get("value") or v.get("name")) == istenen), None)
        if not v:
            # Renk listesinde yoksa "Çok Renkli"/"Şeffaf" yedek
            alt = [x for x in vals if (x.get("value") or x.get("name")) in ("Şeffaf", "Çok Renkli", "Siyah")]
            v = alt[0] if alt else None
        if v:
            out.append({"attributeId": a["id"], "attributeValueId": v["id"]})
        elif a.get("isRequired"):
            eksik.append(ad + "=" + istenen)
    return out, eksik


def urunler():
    ty = {u["stokKodu"]: u for u in json.load(open(os.path.join(KOK, "content", "trendyol_yeni_10.json"), encoding="utf-8"))["urunler"]}
    for b in json.load(open(os.path.join(KOK, "content", "trendyol_yeni_10.json"), encoding="utf-8"))["beklemede"]:
        ty.setdefault(b["stokKodu"], b)
    mid = marka_id()
    out, rapor = [], []
    for u in json.load(open(os.path.join(KOK, "content", "n11_yeni_10.json"), encoding="utf-8")):
        sk = u["stokKodu"].replace("-N11", "")
        anah, secim = URUN[sk]
        cid, kom = KAT[anah]
        p_ty = float(ty[sk]["fiyat"])
        p = fiyat(p_ty, kom)
        attrs, eksik = ozellikler(anah, secim)
        out.append({
            "name": u["ad"][:150], "displayName": u["ad"][:150],
            "description": _duz_metin(u["aciklama"])[:5000],
            "brandId": mid, "categoryId": cid,
            "code": str(u["barkod"]), "stockCode": sk, "groupCode": sk,
            "barcode": str(u["barkod"]),
            "listPrice": float(p), "salePrice": float(p),
            "vatRate": 20, "stockCount": int(u["stok"]), "desi": 1,
            "images": [{"imageurl": g} for g in u["gorseller"][:8]],
            "attributes": attrs,
        })
        rapor.append("  %-12s %-10s kom=%.0f%% TY=%.0f -> PZ=%d  ozellik=%d%s" % (
            sk, anah, kom * 100, p_ty, p, len(attrs), ("  EKSIK:" + ",".join(eksik)) if eksik else ""))
    return out, rapor


def main():
    out, rapor = urunler()
    print("\n".join(rapor))
    json.dump(out, open(os.path.join(KOK, "content", "pazarama_yeni_10.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if "--sonuc" in sys.argv:
        sonuc(sys.argv[sys.argv.index("--sonuc") + 1]); return
    sec = None
    if "--tek" in sys.argv:
        k = sys.argv[sys.argv.index("--tek") + 1]
        sec = [x for x in out if x["stockCode"] == k]
    elif "--hepsi" in sys.argv:
        sec = out
    if sec:
        r = pz.post("/product/create", {"products": sec})
        print("HTTP", r.status_code, r.text[:700])
        try:
            j = r.json()
            print("hatalar:", _hatalari_ayikla(j))
            print("batch:", (j.get("data") or {}).get("batchRequestId"))
        except Exception as e:
            print("json yok", e)


if __name__ == "__main__":
    main()
