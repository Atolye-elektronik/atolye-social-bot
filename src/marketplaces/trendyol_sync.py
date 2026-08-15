"""
Scheduled job: pull Trendyol orders that are awaiting shipment and surface
them as a GitHub issue so they show up somewhere you'll actually see them
(no Slack/email connector needed — this repo's Issues tab becomes the inbox).

Run manually:   python src/marketplaces/trendyol_sync.py
Run in CI:      via .github/workflows/trendyol-sync.yml (scheduled + manual button)

What it does each run:
1. Fetches orders with status Created or Picking (i.e. not yet shipped).
2. Writes the raw snapshot to state/trendyol_orders.json (committed by the
   workflow, so you get a diff-able history of what Trendyol reported).
3. Opens or updates a single "open" GitHub issue titled
   "Trendyol: Kargoya verilmesi gereken siparişler" listing them, so it's
   always up to date instead of spamming a new issue every run.

NOTE ON UNVERIFIED FIELDS: I could not make a live test call against the
real Trendyol API from the environment that wrote this script (its network
egress is sandboxed), so the exact field names below (`orderNumber`,
`status`, `lines`, etc.) come from the published API docs rather than a
live response sample. Run this once by hand first (see README) and check
the printed output / state/trendyol_orders.json before trusting the
GitHub issue content — if Trendyol's actual response uses slightly
different field names, tweak the `_summarize_package` function below.
"""

import json
from pathlib import Path

import requests

from issue_tracker import upsert_issue
from trendyol_client import get_orders

STATE_DIR = Path(__file__).resolve().parents[2] / "state"
STATE_FILE = STATE_DIR / "trendyol_orders.json"

ISSUE_TITLE = "Trendyol: Kargoya verilmesi gereken siparişler"


def _summarize_package(pkg):
    """Best-effort summary of one order/shipment package. See NOTE above
    about field names not being live-verified."""
    order_number = pkg.get("orderNumber") or pkg.get("id") or "?"
    status = pkg.get("status") or pkg.get("shipmentPackageStatus") or "?"
    lines = pkg.get("lines") or []
    items_desc = ", ".join(
        f"{l.get('productName', l.get('barcode', '?'))} x{l.get('quantity', 1)}"
        for l in lines
    ) or "(ürün detayı yok)"
    return f"- Sipariş **{order_number}** — durum: `{status}` — {items_desc}"


def fetch_pending_orders():
    all_packages = []
    for status in ("Created", "Picking"):
        try:
            data = get_orders(status=status, size=200)
        except requests.HTTPError as e:
            print(f"UYARI: status={status} çekilirken hata: {e}")
            continue
        packages = data.get("content", data.get("shipmentPackages", []))
        all_packages.extend(packages)
    return all_packages


def save_state(packages):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(packages, ensure_ascii=False, indent=2))


def report_issue(packages):
    if not packages:
        body = "Şu anda kargoya verilmeyi bekleyen Trendyol siparişi yok. ✅"
    else:
        body = (
            f"Son kontrolde kargoya verilmesi gereken **{len(packages)}** sipariş bulundu:\n\n"
            + "\n".join(_summarize_package(p) for p in packages)
            + "\n\n_Bu issue her çalıştırmada otomatik güncellenir (trendyol_sync.py)._"
        )

    upsert_issue(
        ISSUE_TITLE,
        body,
        labels=["trendyol", "siparis"],
        create_if_missing=bool(packages),
    )


def main():
    packages = fetch_pending_orders()
    print(f"{len(packages)} bekleyen sipariş paketi bulundu.")
    save_state(packages)
    report_issue(packages)


if __name__ == "__main__":
    main()
