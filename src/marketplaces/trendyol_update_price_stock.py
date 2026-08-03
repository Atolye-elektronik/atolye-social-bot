"""
Manual price/stock update helper for Trendyol.

This is intentionally NOT part of the scheduled workflow — updating prices
or stock automatically without a defined business rule (what price? based
on what?) is risky, so this is a script you run on demand (or trigger via
the "Run workflow" button in GitHub Actions with inputs) whenever you have
specific numbers to push.

Usage (local):
    python src/marketplaces/trendyol_update_price_stock.py items.json

items.json format:
[
  {"barcode": "8680000000123", "quantity": 50, "salePrice": 199.90, "listPrice": 229.90},
  {"barcode": "8680000000456", "quantity": 0,  "salePrice": 149.90, "listPrice": 149.90}
]
"""

import json
import sys
import time

from trendyol_client import get_batch_request_result, update_price_and_inventory


def main():
    if len(sys.argv) != 2:
        print("Kullanım: python trendyol_update_price_stock.py items.json")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        items = json.load(f)

    print(f"{len(items)} ürün için fiyat/stok güncelleme isteği gönderiliyor...")
    result = update_price_and_inventory(items)
    batch_id = result.get("batchRequestId")
    print(f"Gönderildi. batchRequestId: {batch_id}")

    if not batch_id:
        return

    # Trendyol processes batches async — poll a few times for the result.
    for attempt in range(5):
        time.sleep(3)
        status = get_batch_request_result(batch_id)
        print(f"Deneme {attempt + 1}: {json.dumps(status, ensure_ascii=False)[:500]}")
        if status.get("status") not in ("PROCESSING", None):
            break


if __name__ == "__main__":
    main()
