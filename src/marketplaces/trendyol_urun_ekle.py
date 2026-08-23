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
        for a in oz.get("categoryAttributes", []):
            if a["attribute"]["name"] == "Menşei":
                for v in a.get("attributeValues") or []:
                    if v["name"] in ("CN", "TR", "Çin", "Türkiye"):
                        print("  MENSEI", v["id"], v["name"])
    # kargo id: mevcut bir ürünün cargoCompanyId'si
    try:
        d = tc.get_approved_products(page=0, size=5)
        for c in d.get("content", [])[:5]:
            print("Mevcut urun kargo:", c.get("title", "")[:40], c.get("cargoCompanyId"), "| desi", c.get("dimensionalWeight"))
    except Exception as e:  # noqa: BLE001
        print("Mevcut urun okunamadi:", e)
    try:
        d = tc.get_products_v1(page=0, size=3)
        for c in d.get("content", [])[:3]:
            print("V1 urun kargo:", c.get("title", "")[:40], c.get("cargoCompanyId"), "| desi", c.get("dimensionalWeight"))
    except Exception as e:  # noqa: BLE001
        print("V1 okunamadi:", e)
    for yol in ("/sellers/%s/cargo-providers" % tc.SUPPLIER_ID, "/product/cargo-providers", "/order/sellers/%s/cargo-providers" % tc.SUPPLIER_ID):
        try:
            print("Kargo", yol, str(_get(yol))[:600])
        except Exception as e:  # noqa: BLE001
            print("Kargo", yol, "->", str(e)[:80])


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
            "origin": cfg.get("mensei", "CN"),
            "listPrice": float(u["fiyat"]),
            "salePrice": float(u["fiyat"]),
            "vatRate": 20,
            "cargoProviders": [cfg.get("kargoKodu", "SURATMP")],
            "images": [{"url": g} for g in u["gorseller"][:8]],
            "attributes": [
                {"attributeId": a["attributeId"], **({"attributeValueId": a["attributeValueId"]} if "attributeValueId" in a else {"customAttributeValue": a["customAttributeValue"]})}
                for a in cfg.get("ozellikler", [])
            ],
        })
    return {"items": items}


def gonder(payload, guncelle=False):
    yol = "/products/unapproved-bulk-update" if guncelle else "/v2/products"
    r = requests.post(f"{tc.BASE_URL}/product/sellers/{tc.SUPPLIER_ID}{yol}",
                      headers=tc._auth_header(), json=payload, timeout=60)
    print(r.status_code, r.text[:1000])
    r.raise_for_status()
    return r.json()


def batch_sonuc(bid):
    r = _get(f"/product/sellers/{tc.SUPPLIER_ID}/products/batch-requests/{bid}")
    print("batch status:", r.get("status"), "| item:", r.get("itemCount"), "| fail:", r.get("failedItemCount"))
    for it in r.get("items", []):
        p = it.get("requestItem", {}).get("product", {})
        print(" ", it.get("status"), p.get("stockCode"), p.get("barcode"), it.get("failureReasons"))
    return r


def onaysizlar():
    for st in ("rejected", "pendingApproval"):
        try:
            d = _get(f"/product/sellers/{tc.SUPPLIER_ID}/products/unapproved", status=st, page=0, size=100)
        except Exception as e:  # noqa: BLE001
            print(st, "okunamadi:", str(e)[:120]); continue
        items = d.get("content", d if isinstance(d, list) else [])
        print(f"== {st}: {len(items)}")
        for it in items:
            print(" ", it.get("stockCode") or it.get("productMainId"), "|", (it.get("title") or "")[:50])
            for r in it.get("rejectReasonDetails") or []:
                print("     -", r.get("rejectReason"), ":", (r.get("rejectReasonDetail") or "")[:160])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--onaysiz", action="store_true")
    ap.add_argument("--kategori", help="kesfet icin kategori adi (config yerine)")
    ap.add_argument("--sku", help="virgullu stok kodu listesi: sadece bunlari gonder")
    ap.add_argument("--guncelle", action="store_true", help="onaysiz urunleri guncelle (unapproved-bulk-update)")
    ap.add_argument("--stok", action="store_true", help="config'teki stok/fiyati price-and-inventory ile gonder")
    ap.add_argument("--not-ekle", help="virgullu stokCode listesi: onayli urun aciklamasinin basina sema notu ekle")
    ap.add_argument("--kesfet", action="store_true")
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--gonder", action="store_true")
    ap.add_argument("--batch")
    a = ap.parse_args()
    cfg = json.loads(URUN_DOSYASI.read_text(encoding="utf-8"))
    if a.sku:
        secim = {x.strip() for x in a.sku.split(",")}
        cfg["urunler"] = [u for u in cfg["urunler"] if u["stokKodu"] in secim]
    if a.kesfet:
        if a.kategori: cfg["kategori"] = a.kategori
        kesfet(cfg)
    if a.kuru:
        print(json.dumps(payload_kur(cfg), ensure_ascii=False, indent=2)[:8000])
    if a.gonder:
        sonuc = gonder(payload_kur(cfg), guncelle=a.guncelle)
        KAYIT.parent.mkdir(exist_ok=True)
        eski = json.loads(KAYIT.read_text(encoding="utf-8")) if KAYIT.exists() else {}
        for u in cfg["urunler"]:
            eski[u["stokKodu"]] = {"barkod": u["barkod"], "batchRequestId": sonuc.get("batchRequestId")}
        KAYIT.write_text(json.dumps(eski, ensure_ascii=False, indent=2), encoding="utf-8")
        print("batchRequestId:", sonuc.get("batchRequestId"))
    if a.batch:
        batch_sonuc(a.batch)
    if a.onaysiz:
        onaysizlar()
    if a.stok:
        items = [{"barcode": u["barkod"], "quantity": int(u["stok"]), "salePrice": float(u["fiyat"]), "listPrice": float(u["fiyat"])} for u in cfg["urunler"]]
        print(tc.update_price_and_inventory(items))
    if a.not_ekle:
        NOT = ('<p><strong>Bağlantı şeması ve hazır Arduino kodu ile gönderilir.</strong> Kutuda A4 renkli bağlantı şeması bulunur; '
               'kod ve adım adım kurulum anlatımı paketle birlikte verilir.</p>')
        ESKI_NOT = ('<p><strong>Bağlantı şeması ve hazır Arduino kodu ile gönderilir.</strong> Kutuda A4 renkli bağlantı şeması bulunur; '
                    'kod ve adım adım anlatım atolyeelektronik.com blogumuzdadır.</p>')
        istenen = {x.strip() for x in a.not_ekle.split(",")}
        guncel = []
        for _, p in tc.iter_all_products(size=100):
            for v in p.get("variants", [p]):
                sc = v.get("stockCode") or p.get("stockCode")
                if any(k in (p.get("title") or "") for k in ("Kiti", "Seti")):
                    print("  mevcut:", sc, "|", (p.get("title") or "")[:50], "| contentId", p.get("contentId") or p.get("id"))
                if sc in istenen:
                    desc = p.get("description") or ""
                    if ESKI_NOT in desc:
                        desc = desc.replace(ESKI_NOT, "")
                    elif NOT in desc:
                        print("zaten var:", sc); continue
                    desc = NOT + desc
                    if "atolyeelektronik" in desc.lower():
                        print("UYARI site adi var, temizleniyor:", sc)
                        desc = re.sub(r"(?i)atolyeelektronik\.com", "", desc)
                    guncel.append({"contentId": p.get("contentId") or p.get("id"), "description": desc})
                    print("guncellenecek:", sc, v.get("barcode") or p.get("barcode"))
        if guncel:
            r = requests.post(f"{tc.BASE_URL}/product/sellers/{tc.SUPPLIER_ID}/products/content-bulk-update",
                              headers=tc._auth_header(), json={"items": guncel}, timeout=60)
            print(r.status_code, r.text[:500])


if __name__ == "__main__":
    main()
