"""
Manual price/stock update helper for Hepsiburada.

This is intentionally NOT part of the scheduled workflow — updating prices
or stock automatically without a defined business rule is risky, so this is
a script you run on demand whenever you have specific numbers to push.

Usage (local):
    python src/marketplaces/hepsiburada_update_price_stock.py items.json

items.json format (fiyat, stok veya ikisi birden — hangisi varsa o gönderilir):
[
  {"hepsiburadaSku": "HBV000ABC123", "merchantSku": "SKU-1", "availableStock": 50, "price": 199.90},
  {"hepsiburadaSku": "HBV000DEF456", "merchantSku": "SKU-2", "availableStock": 0}
]
"""

import json
import sys
import time

from hepsiburada_client import (
    get_price_upload_status,
    get_stock_upload_status,
    update_price,
    update_stock,
)


def _poll(get_status, upload_id, label):
    # Hepsiburada processes uploads async — poll a few times for the result.
    for attempt in range(5):
        time.sleep(3)
        status = get_status(upload_id)
        print(f"{label} deneme {attempt + 1}: {json.dumps(status, ensure_ascii=False)[:500]}")
        if str(status.get("status", "")).lower() not in ("", "pending", "processing", "inprogress"):
            break


def main():
    if len(sys.argv) != 2:
        print("Kullanım: python hepsiburada_update_price_stock.py items.json")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        items = json.load(f)

    stock_items = [
        {k: i[k] for k in ("hepsiburadaSku", "merchantSku", "availableStock") if k in i}
        for i in items
        if "availableStock" in i
    ]
    price_items = [
        {k: i[k] for k in ("hepsiburadaSku", "merchantSku", "price") if k in i}
        for i in items
        if "price" in i
    ]

    if stock_items:
        print(f"{len(stock_items)} ürün için stok güncelleme isteği gönderiliyor...")
        result = update_stock(stock_items)
        upload_id = result.get("id") or result.get("uploadId")
        print(f"Gönderildi. upload id: {upload_id}")
        if upload_id:
            _poll(get_stock_upload_status, upload_id, "Stok")

    if price_items:
        print(f"{len(price_items)} ürün için fiyat güncelleme isteği gönderiliyor...")
        result = update_price(price_items)
        upload_id = result.get("id") or result.get("uploadId")
        print(f"Gönderildi. upload id: {upload_id}")
        if upload_id:
            _poll(get_price_upload_status, upload_id, "Fiyat")

    if not (stock_items or price_items):
        print("items.json içinde availableStock veya price alanı bulunamadı.")


if __name__ == "__main__":
    main()
