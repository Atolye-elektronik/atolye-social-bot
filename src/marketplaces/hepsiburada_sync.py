"""
Scheduled job: pull Hepsiburada orders that are awaiting shipment and surface
them as a GitHub issue, exactly like trendyol_sync.py does for Trendyol
(this repo's Issues tab is the shared inbox for both marketplaces).

Run manually:   python src/marketplaces/hepsiburada_sync.py
Run in CI:      via .github/workflows/hepsiburada-sync.yml (scheduled + manual button)

What it does each run:
1. Fetches unpacked new order items (OMS /orders) and packed-but-unshipped
   packages (OMS /packages).
2. Writes the raw snapshot to state/hepsiburada_orders.json (committed by
   the workflow, so you get a diff-able history).
3. Opens or updates a single "open" GitHub issue titled
   "Hepsiburada: Kargoya verilmesi gereken siparişler".

Live-verified against the SIT (test) environment on 2026-08-09:
- /orders returns {"totalCount", "limit", "offset", "pageCount", "items": [...]}
- /packages returns a bare JSON array
- /listings returns {"listings": [...]} with hepsiburadaSku/merchantSku/
  price/availableStock/isSalable fields
Order item/package detail fields (`orderNumber`, `productName`, ...) could
not be exercised because the test account had no open orders — if the
issue output looks off once real orders arrive, tweak the summarize
functions below.
"""

import json
import os
from pathlib import Path

import requests

from hepsiburada_client import get_new_order_items, get_packages

STATE_DIR = Path(__file__).resolve().parents[2] / "state"
STATE_FILE = STATE_DIR / "hepsiburada_orders.json"

ISSUE_TITLE = "Hepsiburada: Kargoya verilmesi gereken siparişler"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY")  # "owner/repo", auto-set in Actions


def _summarize_order_item(item):
    """Best-effort summary of one unpacked order item. See NOTE above
    about field names not being live-verified."""
    order_number = item.get("orderNumber") or item.get("orderId") or "?"
    name = item.get("productName") or item.get("name") or item.get("merchantSku") or "?"
    qty = item.get("quantity") or 1
    return f"- Sipariş **{order_number}** — `paketlenmedi` — {name} x{qty}"


def _summarize_package(pkg):
    package_number = pkg.get("packageNumber") or pkg.get("id") or "?"
    items = pkg.get("items") or pkg.get("lines") or []
    items_desc = ", ".join(
        f"{i.get('productName', i.get('merchantSku', '?'))} x{i.get('quantity', 1)}"
        for i in items
    ) or "(ürün detayı yok)"
    return f"- Paket **{package_number}** — `kargo bekliyor` — {items_desc}"


def _extract_list(data):
    """HB endpoints wrap the list either as a bare array or under a key."""
    if isinstance(data, list):
        return data
    for key in ("items", "content", "data", "listings"):
        if isinstance(data.get(key), list):
            return data[key]
    return []


def fetch_pending():
    new_items, packages = [], []
    try:
        new_items = _extract_list(get_new_order_items(limit=100))
    except requests.HTTPError as e:
        print(f"UYARI: yeni siparişler çekilirken hata: {e}")
    try:
        packages = _extract_list(get_packages(limit=100))
    except requests.HTTPError as e:
        print(f"UYARI: paketler çekilirken hata: {e}")
    return new_items, packages


def save_state(new_items, packages):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(
            {"newOrderItems": new_items, "packages": packages},
            ensure_ascii=False,
            indent=2,
        )
    )


def upsert_github_issue(new_items, packages):
    if not (GITHUB_TOKEN and GITHUB_REPOSITORY):
        print("GITHUB_TOKEN / GITHUB_REPOSITORY yok — issue adımı atlanıyor (yerel çalıştırma).")
        return

    api = f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    total = len(new_items) + len(packages)
    if not total:
        body = "Şu anda kargoya verilmeyi bekleyen Hepsiburada siparişi yok. ✅"
    else:
        lines = [f"Son kontrolde işlem bekleyen **{total}** kayıt bulundu:", ""]
        lines += [_summarize_order_item(i) for i in new_items]
        lines += [_summarize_package(p) for p in packages]
        lines += ["", "_Bu issue her çalıştırmada otomatik güncellenir (hepsiburada_sync.py)._"]
        body = "\n".join(lines)

    # find existing open issue with this title
    resp = requests.get(
        f"{api}/issues", headers=headers, params={"state": "open", "per_page": 100}, timeout=30
    )
    resp.raise_for_status()
    existing = next((i for i in resp.json() if i.get("title") == ISSUE_TITLE), None)

    if existing:
        requests.patch(
            f"{api}/issues/{existing['number']}", headers=headers, json={"body": body}, timeout=30
        ).raise_for_status()
        print(f"Issue #{existing['number']} güncellendi.")
    elif total:
        r = requests.post(
            f"{api}/issues",
            headers=headers,
            json={"title": ISSUE_TITLE, "body": body, "labels": ["hepsiburada", "siparis"]},
            timeout=30,
        )
        r.raise_for_status()
        print(f"Yeni issue oluşturuldu: #{r.json()['number']}")
    else:
        print("Bekleyen sipariş yok, yeni issue açılmadı.")


def main():
    new_items, packages = fetch_pending()
    print(f"{len(new_items)} paketlenmemiş kalem, {len(packages)} kargo bekleyen paket bulundu.")
    save_state(new_items, packages)
    upsert_github_issue(new_items, packages)


if __name__ == "__main__":
    main()
