"""
Trendyol Marketplace API client — order fetch + price/stock update.

Reference docs (checked live on 2026-08-03):
- Auth:           https://developers.trendyol.com/docs/2-authorization
- Orders:         https://developers.trendyol.com/v3.0/reference/getshipmentpackages
- Price/Stock:    https://developers.trendyol.com/docs/stok-ve-fiyat-g%C3%BCncelleme-updatepriceandinventory

Credentials come from environment variables (set as GitHub Actions secrets
in CI, or a local .env file for testing on your own machine):
    TRENDYOL_SUPPLIER_ID
    TRENDYOL_API_KEY
    TRENDYOL_API_SECRET

Security note: rotate these in the Trendyol seller panel (Hesabım >
Entegrasyon Bilgileri > Düzenle) if they were ever pasted anywhere public.
"""

import base64
import os
import time
from pathlib import Path

import requests

BASE_URL = "https://apigw.trendyol.com/integration"


def _load_dotenv():
    """Best-effort local .env loader for running this on your own machine.
    In GitHub Actions the real env vars (from secrets) are already set,
    so this is a no-op there (os.environ.get already has the values)."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

SUPPLIER_ID = os.environ.get("TRENDYOL_SUPPLIER_ID")
API_KEY = os.environ.get("TRENDYOL_API_KEY")
API_SECRET = os.environ.get("TRENDYOL_API_SECRET")


def _check_config():
    missing = [
        name
        for name, val in [
            ("TRENDYOL_SUPPLIER_ID", SUPPLIER_ID),
            ("TRENDYOL_API_KEY", API_KEY),
            ("TRENDYOL_API_SECRET", API_SECRET),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            "Eksik ortam değişkeni(leri): " + ", ".join(missing) +
            " — GitHub Actions Secrets veya yerel .env dosyasını kontrol et."
        )


def _auth_header():
    _check_config()
    token = base64.b64encode(f"{API_KEY}:{API_SECRET}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "User-Agent": f"{SUPPLIER_ID} - SelfIntegration",
        "Content-Type": "application/json",
    }


def get_orders(status=None, start_date_ms=None, end_date_ms=None, page=0, size=50):
    """Fetch shipment packages (orders).

    status: Created, Picking, Invoiced, Shipped, Cancelled, Delivered,
            UnDelivered, Returned, AtCollectionPoint, UnSupplied, Awaiting
    """
    if not (start_date_ms and end_date_ms):
        end_date_ms = int(time.time() * 1000)
        start_date_ms = end_date_ms - 14 * 24 * 60 * 60 * 1000  # last 14 days

    params = {
        "startDate": start_date_ms,
        "endDate": end_date_ms,
        "page": page,
        "size": size,
        "orderByField": "PackageLastModifiedDate",
        "orderByDirection": "DESC",
    }
    if status:
        params["status"] = status

    url = f"{BASE_URL}/order/sellers/{SUPPLIER_ID}/orders"
    resp = requests.get(url, headers=_auth_header(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def update_price_and_inventory(items):
    """items: list of {"barcode": str, "quantity": int, "salePrice": float, "listPrice": float}
    Returns the batchRequestId to check via get_batch_request_result()."""
    url = f"{BASE_URL}/inventory/sellers/{SUPPLIER_ID}/products/price-and-inventory"
    resp = requests.post(url, headers=_auth_header(), json={"items": items}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_batch_request_result(batch_request_id):
    url = f"{BASE_URL}/product/sellers/{SUPPLIER_ID}/products/batch-requests/{batch_request_id}"
    resp = requests.get(url, headers=_auth_header(), timeout=30)
    resp.raise_for_status()
    return resp.json()
