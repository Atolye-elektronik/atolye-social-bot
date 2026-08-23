"""
Trendyol'a yeni ürün açma (createProducts) — kendi barkodumuzla, BuyBox'a girmeden.

Kullanım (GitHub Actions üzerinden, TRENDYOL_* secret'ları ile):
    python trendyol_urun_ekle.py --kesfet                # marka/kategori/özellik/kargo id'lerini yazdır
    python trendyol_urun_ekle.py --kuru                  # payload'ı üret, göndermeden yazdır
    python trendyol_urun_ekle.py --gonder                # gönder, batchRequestId yaz
    python trendyol_urun_ekle.py --batch <id>            # sonuç sorgula

Ürün listesi content/trendyol_yeni_urunler.json dosyasından okunur.
Docs: https://developers.trendyol.com/docs/category/%C3%BCr%C3%BCn-entegrasyonu
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trendyol_client as tc  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
URUN_DOSYASI = ROOT / "content" / "trendyol_yeni_urunler.json"
KAYIT = ROOT / "state" / "trendyol_urunler.json"


def _get(path, **params):
    r = requests.get(f"{tc.BASE_URL}{path}", headers=tc._auth_header(), params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def marka_bul(ad: str) -> int | None:
    data = _get("/product/brands/by-name", name=ad)
    for b in data or []:
        if b.get("name", "").strip().lower() == ad.strip().lower():
            return b["id"]
    return (data or [{}])[0].get("id")


def kategori_bul(ad: str):
    agac = _get("/product/product-categories")
    bulunan = []

    def gez(dugum, yol):
        y = yol + [dugum["name"]]
        if dugum["name"].strip().lower() == ad.strip().lower():
            bulunan.append((dugum["id"], " > ".join(y)))
        for c in dugum.get("subCategories", []) or []:
            gez(c, y)

    for k in agac.get("categories", []):
        gez(k, [])
    return bulunan


def kategori_ozellikleri(cid: int):
    return _get(f"/product/product-categories/{cid}/attributes")


def kargo_firmalari():
    return _get("/sellers/cargo-providers") if False else _get("/product/shipment-providers")


def kesfet(cfg):
    print("Marka:", cfg["marka"], "->", marka_bul(cfg["marka"]))
    for cid, yol in kategori_bul(cfg["kategori"]):
        print("Kategori:", cid, yol)
        oz = kategori_ozellikleri(cid)
        for a in oz.get("categoryAttributes", []):
            at = a["attribute"]
            print(f"  attr {at['id']:>6} {at['name']:<25} zorunlu={a.get('required')} varyant={a.get('varianter')} "
                  f"serbest={a.get('allowCustom')} degerler={[ (v['id'], v['name']) for v in (a.get('attributeValues') or [])[:12] ]}")
    try:
        for s in kargo_firmalari():
            print("Kargo:", s)
    except Exception as e:  # noqa: BLE001
        print("Kargo listesi alınamadı:", e)


def payload_kur(cfg):
    marka_id = cfg.get("markaId") or marka_bul(cfg["marka"])
    kats = kategori_bul(cfg["kategori"])
    if not kats:
        raise SystemExit(f"Kategori bulunamadı: {cfg['kategori']}")
    cid = cfg.get("kategoriId") or kats[0][0]
    items = []
    for u in cfg["urunler"]:
        items.append({
            "barcode": u["barkod"],
            "title": u["ad"][:100],
            "productMainId": u["modelKodu"],
            "brandId": marka_id,
            "categoryId": cid,
            "quantity": int(u["stok"]),
            "stockCode": u["stokKodu"],
            "dimensionalWeight": u.get("desi", 1),
            "description": u["aciklama"],
            "currencyType": "TRY",
            "listPrice": float(u["fiyat"]),
            "salePrice": float(u["fiyat"]),
            "vatRate": 20,
            "cargoCompanyId": cfg["kargoId"],
            "images": [{"url": g} for g in u["gorseller"][:8]],
            "attributes": [
                {"attributeId": a["attributeId"], **({"attributeValueId": a["attributeValueId"]} if "attributeValueId" in a else {"customAttributeValue": a["customAttributeValue"]})}
                for a in cfg.get("ozellikler", [])
            ],
        })
    return {"items": items}


def gonder(payload):
    r = requests.post(f"{tc.BASE_URL}/product/sellers/{tc.SUPPLIER_ID}/products",
                      headers=tc._auth_header(), json=payload, timeout=60)
    print(r.status_code, r.text[:1000])
    r.raise_for_status()
    return r.json()


def batch_sonuc(bid):
    r = _get(f"/product/sellers/{tc.SUPPLIER_ID}/products/batch-requests/{bid}")
    print(json.dumps(r, ensure_ascii=False, indent=2)[:6000])
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kesfet", action="store_true")
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--gonder", action="store_true")
    ap.add_argument("--batch")
    a = ap.parse_args()
    cfg = json.loads(URUN_DOSYASI.read_text(encoding="utf-8"))
    if a.kesfet:
        kesfet(cfg)
    if a.kuru:
        print(json.dumps(payload_kur(cfg), ensure_ascii=False, indent=2)[:8000])
    if a.gonder:
        sonuc = gonder(payload_kur(cfg))
        KAYIT.parent.mkdir(exist_ok=True)
        eski = json.loads(KAYIT.read_text(encoding="utf-8")) if KAYIT.exists() else {}
        for u in cfg["urunler"]:
            eski[u["stokKodu"]] = {"barkod": u["barkod"], "batchRequestId": sonuc.get("batchRequestId")}
        KAYIT.write_text(json.dumps(eski, ensure_ascii=False, indent=2), encoding="utf-8")
        print("batchRequestId:", sonuc.get("batchRequestId"))
    if a.batch:
        batch_sonuc(a.batch)


if __name__ == "__main__":
    main()
