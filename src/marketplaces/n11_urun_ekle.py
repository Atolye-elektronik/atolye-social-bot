"""N11'e urun acma - Trendyol urun listesini yeniden kullanir.

Kullanim (N11_API_KEY / N11_API_SECRET tanimli olmali):
    python n11_urun_ekle.py --test                  # anahtarlari dogrula
    python n11_urun_ekle.py --kategori-ara yankeski # kategori id bul
    python n11_urun_ekle.py --ozellik 1000123       # kategorinin zorunlu ozellikleri
    python n11_urun_ekle.py --kuru --sku AEKRK5     # payload'i goster
    python n11_urun_ekle.py --gonder --sku AEKRK5   # gonder
    python n11_urun_ekle.py --gorev <taskId>        # sonucu sorgula

Urun listesi content/trendyol_yeni_urunler.json'dan okunur (ayni urunler).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import n11_client as nc  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
URUN_DOSYASI = ROOT / "content" / "trendyol_yeni_urunler.json"
N11_EK = ROOT / "content" / "n11_ek_bilgi.json"   # sku -> {kategoriId, ozellikler}
KAYIT = ROOT / "state" / "n11_urunler.json"


def _cfg() -> dict:
    return json.loads(URUN_DOSYASI.read_text(encoding="utf-8"))


def _ek() -> dict:
    return json.loads(N11_EK.read_text(encoding="utf-8")) if N11_EK.exists() else {}


def test():
    r = nc.get("/cdn/categories")
    print("HTTP", r.status_code)
    print(r.text[:600])


def kategori_ara(kelime: str):
    r = nc.get("/cdn/categories")
    if r.status_code != 200:
        print("HTTP", r.status_code, r.text[:300]); return
    kok = r.json()
    bulunan = []

    def gez(dugumler, yol=""):
        for d in dugumler or []:
            ad = d.get("name", "")
            tam = f"{yol} > {ad}" if yol else ad
            if kelime.lower() in ad.lower():
                bulunan.append((d.get("id"), tam))
            gez(d.get("subCategories"), tam)

    gez(kok if isinstance(kok, list) else kok.get("categories"))
    if not bulunan:
        print(f"'{kelime}' bulunamadi. Alt kategoriler tek tek cekilmeli:")
        print("  python n11_urun_ekle.py --alt <kategoriId>")
    for kid, yol in bulunan[:25]:
        print(f"{kid:>10}  {yol}")


def alt(kategori_id: str):
    r = nc.get(f"/cdn/category/{kategori_id}/sub-categories")
    print("HTTP", r.status_code)
    print(r.text[:2000])


def ozellik(kategori_id: str):
    r = nc.get(f"/cdn/category/{kategori_id}/attribute")
    if r.status_code != 200:
        print("HTTP", r.status_code, r.text[:400]); return
    for a in (r.json() or {}).get("categoryAttributes", r.json() if isinstance(r.json(), list) else []):
        zor = a.get("mandatory", a.get("required"))
        print(f"  attr {a.get('id')} {a.get('name'):<28} zorunlu={zor} "
              f"degerler={[(v.get('id'), v.get('name')) for v in (a.get('attributeValues') or [])][:6]}")


def payload_kur(cfg, ek) -> dict:
    urunler = []
    for u in cfg["urunler"]:
        e = ek.get(u["stokKodu"], {})
        urunler.append({
            "title": u["ad"][:100],
            "description": u["aciklama"],
            "categoryId": e.get("kategoriId"),
            "currencyType": "TL",
            "productMainId": u["modelKodu"],
            "preparingDay": 1,
            "shipmentTemplate": e.get("kargoSablonu", "Standart"),
            "stockCode": u["stokKodu"],
            "barcode": u["barkod"],
            "quantity": u["stok"],
            "salePrice": float(u["fiyat"]),
            "listPrice": float(u["fiyat"]),
            "attributes": e.get("ozellikler", []),
            "images": [{"url": g, "order": i + 1} for i, g in enumerate(u["gorseller"])],
        })
    return {"integrator": nc.ENTEGRATOR, "skus": urunler}


def gonder(govde):
    r = nc.post("/ms/product/tasks/product-create", govde)
    print("HTTP", r.status_code)
    print(r.text[:800])
    try:
        return r.json()
    except Exception:
        return {}


def gorev(task_id: str):
    r = nc.get("/ms/product/task-details/page-query", taskId=task_id, pageSize=100, page=0)
    print("HTTP", r.status_code)
    print(r.text[:2000])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--kategori-ara")
    ap.add_argument("--alt")
    ap.add_argument("--ozellik")
    ap.add_argument("--sku", help="virgullu stok kodu listesi")
    ap.add_argument("--kuru", action="store_true")
    ap.add_argument("--gonder", action="store_true")
    ap.add_argument("--gorev")
    a = ap.parse_args()

    if a.test:
        test(); return
    if a.kategori_ara:
        kategori_ara(a.kategori_ara); return
    if a.alt:
        alt(a.alt); return
    if a.ozellik:
        ozellik(a.ozellik); return
    if a.gorev:
        gorev(a.gorev); return

    cfg = _cfg()
    if a.sku:
        secim = {x.strip() for x in a.sku.split(",")}
        cfg["urunler"] = [u for u in cfg["urunler"] if u["stokKodu"] in secim]
    ek = _ek()

    eksik = [u["stokKodu"] for u in cfg["urunler"] if not ek.get(u["stokKodu"], {}).get("kategoriId")]
    if eksik:
        print("UYARI: kategoriId eksik ->", ", ".join(eksik))
        print("content/n11_ek_bilgi.json icine sku basina kategoriId + ozellikler yaz.")

    if a.kuru:
        print(json.dumps(payload_kur(cfg, ek), ensure_ascii=False, indent=2)[:8000]); return
    if a.gonder:
        if eksik:
            raise SystemExit("kategoriId eksikken gonderilmez.")
        sonuc = gonder(payload_kur(cfg, ek))
        KAYIT.parent.mkdir(exist_ok=True)
        eski = json.loads(KAYIT.read_text(encoding="utf-8")) if KAYIT.exists() else {}
        for u in cfg["urunler"]:
            eski[u["stokKodu"]] = {"barkod": u["barkod"], "taskId": sonuc.get("id") or sonuc.get("taskId")}
        KAYIT.write_text(json.dumps(eski, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
