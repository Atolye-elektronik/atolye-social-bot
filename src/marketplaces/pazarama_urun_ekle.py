"""Pazarama'ya urun ekler. Kaynak: state/trendyol_tam_katalog.json

Pazarama'nin hata mesaji tuzagi: dogrulama hatalarinin yanina her zaman
"Isleminiz su anda gerceklestirilemiyor. Lutfen daha sonra tekrar deneyiniz."
kapsayici metnini ekliyor. Bu metin TEK BASINA sunucu arizasi anlamina gelmez —
`errors` dizisinden onu filtreleyip digerlerine bakmak gerekir. (03.09'da bu
yuzden yanlis teshis kondu, bir gece kaybedildi.)

Kullanim:
    python -m src.marketplaces.pazarama_urun_ekle --liste
    python -m src.marketplaces.pazarama_urun_ekle --tek AESARJKT1
    python -m src.marketplaces.pazarama_urun_ekle --hepsi
    python -m src.marketplaces.pazarama_urun_ekle --sonuc <batchRequestId>
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import sys

from . import pazarama_client as pz

KATALOG = pathlib.Path("state/trendyol_tam_katalog.json")
MARKA = pathlib.Path("state/pazarama_marka.json")
EK_GORSEL = pathlib.Path("state/pazarama_ek_gorsel.json")
BATCH = pathlib.Path("state/pazarama_batch.json")

# Pazarama kategori GUID'leri. Trendyol kategori adi -> Pazarama GUID.
# Agacin tamami: state/pazarama_kategoriler.json
KATEGORI = {
    "Elektronik Devre Elemanı": "5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9",
    "Robotik Malzeme": "5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9",
    "Akıllı Sensörler": "5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9",
    "Bilgisayar Yedek Parça": "5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9",
    "RC Yedek Parça": "5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9",
    "Eğitici Oyuncak": "5fcd4444-87f0-4f3a-8ecf-3df2a91bd7b9",
    "Lehim & Havya": "d76b5570-d87e-4ae1-ba5f-8e444dc9365a",
    "Yan Keski": "700bd912-f103-4288-adc5-f5c276bea981",
    "Pense": "0498d72e-a1ad-43b8-a6ac-aaddd0c545a1",
    "Kargaburun": "f11e9ba6-6ae2-429f-91cf-113e63c22786",
    "Multimetre": "be7b54f0-8998-41e5-9c57-057b43a9c51f",
    "Ölçüm Cihazı": "be7b54f0-8998-41e5-9c57-057b43a9c51f",
    "Takım Çantası & Avadanlık": "38210217-b841-4368-9f13-90f10482977e",
    "Saklama Kutusu": "38210217-b841-4368-9f13-90f10482977e",
    "Defter": "ac6c409f-f2f5-4a9b-8e15-d6ca0604b02b",
}

# Kategorisi eslenmemis urunler atlanir; asagidakiler bilincli disarida.
ATLA = {"Hobi Makineleri ve Aksesuarları", "El Aletleri Aksesuar Seti", "Tornavida"}

GENEL_HATA = "şu anda gerçekleştirilemiyor"


def _duz_metin(ham: str) -> str:
    """Trendyol aciklamasi HTML; Pazarama duz metin istiyor."""
    metin = re.sub(r"<br\s*/?>", "\n", ham or "")
    metin = re.sub(r"</(p|div|li|tr)>", "\n", metin)
    metin = re.sub(r"<li>", "• ", metin)
    metin = re.sub(r"<[^>]+>", "", metin)
    metin = html.unescape(metin)
    metin = re.sub(r"[ \t]+", " ", metin)
    metin = re.sub(r"\n{3,}", "\n\n", metin)
    return metin.strip()


def _ek_gorseller() -> dict[str, list[str]]:
    if not EK_GORSEL.exists():
        return {}
    return {k["sku"]: k["gorseller"] for k in json.loads(EK_GORSEL.read_text(encoding="utf-8"))}


def katalog() -> list[dict]:
    return json.loads(KATALOG.read_text(encoding="utf-8"))


def marka_id() -> str:
    return json.loads(MARKA.read_text(encoding="utf-8"))["id"]


def urun_kur(u: dict, mid: str, ekler: dict) -> dict | None:
    kat = KATEGORI.get(u.get("categoryName", ""))
    if not kat:
        return None

    gorseller = [g["url"] for g in (u.get("images") or []) if g.get("url")]
    gorseller += ekler.get(u.get("stockCode", ""), [])
    if not gorseller:
        return None

    satis = float(u.get("listPrice") or u.get("salePrice") or 0)
    indirimli = float(u.get("salePrice") or satis)
    if not satis or not indirimli:
        return None

    return {
        "name": u["title"][:150],
        "displayName": u["title"][:150],
        "description": _duz_metin(u.get("description", ""))[:5000],
        "brandId": mid,
        "categoryId": kat,
        "code": u["stockCode"],
        "stockCode": u["stockCode"],
        "groupCode": u.get("productMainId") or u["stockCode"],
        "barcode": str(u["barcode"]),
        "listPrice": satis,
        "salePrice": indirimli,
        "vatRate": int(u.get("vatRate") or 20),
        "stockCount": int(u.get("quantity") or 0),
        "desi": int(u.get("dimensionalWeight") or 1),
        "images": [{"imageurl": g} for g in gorseller[:8]],
        "attributes": [],
    }


def _hatalari_ayikla(cevap: dict) -> list[str]:
    """Kapsayici metni atip gercek dogrulama hatalarini dondurur."""
    d = cevap.get("data") or {}
    hatalar = (d.get("error") or {}).get("errors") or []
    return [h.strip() for h in hatalar if GENEL_HATA not in h]


def gonder(urunler: list[dict]) -> dict:
    r = pz.post("/product/create", {"products": urunler})
    return r.json()


def sonuc(batch_id: str) -> None:
    r = pz.get("/product/getProductBatchResult", batchRequestId=batch_id)
    d = r.json().get("data") or {}
    print("durum:%s  toplam:%s  basarili:%s  basarisiz:%s"
          % (d.get("status"), d.get("totalCount"), d.get("successfulCount"), d.get("failedCount")))
    for p in (d.get("failedProducts") or [])[:15]:
        print("  X %-18s %s" % (p.get("productCode"), p.get("errorReason")))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liste", action="store_true", help="gonderilecek urunleri say, gonderme")
    ap.add_argument("--tek", metavar="STOKKODU", help="tek urun gonder (dogrulama icin)")
    ap.add_argument("--hepsi", action="store_true", help="eslesen tum urunleri gonder")
    ap.add_argument("--sonuc", metavar="BATCHID", help="parti sonucunu sorgula")
    a = ap.parse_args()

    if a.sonuc:
        sonuc(a.sonuc)
        return

    mid, ekler = marka_id(), _ek_gorseller()
    hazir, atlanan = [], []
    for u in katalog():
        p = urun_kur(u, mid, ekler)
        (hazir if p else atlanan).append(p or u.get("stockCode"))

    if a.liste:
        print("hazir: %d   atlanan: %d" % (len(hazir), len(atlanan)))
        for p in hazir[:10]:
            print("  %-16s %s" % (p["stockCode"], p["name"][:60]))
        if atlanan:
            print("atlananlar:", ", ".join(str(x) for x in atlanan[:15]))
        return

    if a.tek:
        secili = [p for p in hazir if p["stockCode"] == a.tek]
        if not secili:
            sys.exit("Bulunamadi: %s  (--liste ile bak)" % a.tek)
        print("Gonderiliyor: %s — %s" % (secili[0]["stockCode"], secili[0]["name"][:60]))
        cevap = gonder(secili)
    elif a.hepsi:
        print("Gonderiliyor: %d urun" % len(hazir))
        cevap = gonder(hazir)
    else:
        ap.print_help()
        return

    hatalar = _hatalari_ayikla(cevap)
    d = cevap.get("data") or {}
    bid = d.get("batchRequestId")
    if hatalar:
        print("DOGRULAMA HATALARI:")
        for h in hatalar:
            print("  -", h)
        return
    print("Kabul edildi. batchRequestId:", bid)
    BATCH.write_text(json.dumps({"batchRequestId": bid}) + "\n", encoding="utf-8")
    print("Sonucu gormek icin:  --sonuc", bid)


if __name__ == "__main__":
    main()
