"""
Hepsiburada listing'lerine fiyat + stok uygula.

Panelden elle eklenen ürünler envantere fiyat 0 / stok 0 olarak düşüyor
(23.08.2026'da görüldü). Bu script content/hepsiburada_kategori.json içindeki
fiyat_override / stok_override tablolarını okur, mağazadaki listing'lerden
merchantSku -> hepsiburadaSku eşlemesini çeker ve listing API'siyle yükler.

Kullanım:
    python hepsiburada_fiyat_stok_uygula.py            # override'daki tüm SKU'lar
    python hepsiburada_fiyat_stok_uygula.py SKU1,SKU2  # sadece bunlar
"""
import json
import sys
import time
from pathlib import Path

from hepsiburada_client import (
    get_listings, get_price_upload_status, get_stock_upload_status, update_price, update_stock,
)

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "content" / "hepsiburada_kategori.json"


def overrides():
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    fiyat, stok = {}, {}
    for grp in cfg.values():
        if isinstance(grp, dict):
            fiyat.update(grp.get("fiyat_override") or {})
            stok.update(grp.get("stok_override") or {})
    return fiyat, stok


def all_listings():
    out, offset = [], 0
    while True:
        page = get_listings(offset=offset, limit=100)
        items = page.get("listings") or page.get("items") or []
        out += items
        if len(items) < 100:
            return out
        offset += 100


def poll(get_status, upload_id, label):
    for i in range(6):
        time.sleep(4)
        st = get_status(upload_id)
        print(f"{label} {i+1}: {json.dumps(st, ensure_ascii=False)[:600]}")
        if str(st.get("status", "")).lower() not in ("", "pending", "processing", "inprogress"):
            return


def sit_testi():
    """SIT (test) ortaminda tam dongu: listing cek, ilk listing'in stok ve fiyatini
    kendi degerleriyle yeniden yukle. Canliya gecis oncesi 'surecleri tamamladik'
    kaniti olarak calistirilir."""
    ls = all_listings()
    print(f"SIT: {len(ls)} listing")
    l = next((x for x in ls if x.get("hepsiburadaSku") and x.get("price")), ls[0])
    base = {"hepsiburadaSku": l["hepsiburadaSku"], "merchantSku": l.get("merchantSku")}
    r = update_stock([{**base, "availableStock": int(l.get("availableStock") or 5)}])
    print("SIT stok upload:", r)
    uid = r.get("id") or r.get("uploadId")
    if uid: poll(get_stock_upload_status, uid, "SIT stok")
    r = update_price([{**base, "price": float(l.get("price") or 100)}])
    print("SIT fiyat upload:", r)
    uid = r.get("id") or r.get("uploadId")
    if uid: poll(get_price_upload_status, uid, "SIT fiyat")


def main():
    if len(sys.argv) > 1 and sys.argv[1].strip() == "--sit-testi":
        sit_testi(); return
    secim = [s.strip() for s in sys.argv[1].split(",")] if len(sys.argv) > 1 and sys.argv[1].strip() else None
    fiyat, stok = overrides()
    skus = secim or sorted(set(fiyat) | set(stok))
    listings = {l.get("merchantSku"): l for l in all_listings()}
    import hepsiburada_client as hc
    print(f"{len(listings)} listing çekildi — base={hc.LISTING_BASE} env={hc.ENV}; örnek: {list(listings)[:40]}")
    p_items, s_items = [], []
    for sku in skus:
        l = listings.get(sku)
        if not l:
            print(f"  ! listing yok: {sku}")
            continue
        base = {"hepsiburadaSku": l["hepsiburadaSku"], "merchantSku": sku}
        if sku in fiyat:
            p_items.append({**base, "price": float(fiyat[sku])})
        if sku in stok:
            s_items.append({**base, "availableStock": int(stok[sku])})
        print(f"  {sku}: fiyat={fiyat.get(sku)} stok={stok.get(sku)} (mevcut {l.get('price')}/{l.get('availableStock')})")
    if p_items:
        r = update_price(p_items); print("fiyat upload:", r)
        uid = r.get("id") or r.get("uploadId")
        if uid: poll(get_price_upload_status, uid, "fiyat")
    if s_items:
        r = update_stock(s_items); print("stok upload:", r)
        uid = r.get("id") or r.get("uploadId")
        if uid: poll(get_stock_upload_status, uid, "stok")


if __name__ == "__main__":
    main()
