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


def get_approved_products(page=0, size=100, status=None, next_page_token=None):
    """V2 approved-product listing.

    Docs: GET /integration/product/sellers/{sellerId}/products/approved
    (Product V1 filtering was retired on 2026-08-10; V2 is content-based —
    `images` and `title` sit at content level, `barcode`/`stockCode` and the
    nested price/stock objects sit on each entry of `variants`.)

    status: archived, blacklisted, locked, onSale, notOnSale
    """
    params = {"page": page, "size": min(size, 100)}
    if status:
        params["status"] = status
    if next_page_token:
        params["nextPageToken"] = next_page_token

    url = f"{BASE_URL}/product/sellers/{SUPPLIER_ID}/products/approved"
    resp = requests.get(url, headers=_auth_header(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_products_v1(page=0, size=100, approved=None, archived=None, on_sale=None):
    """Legacy V1 filterProducts — kept only as a fallback for sellers whose
    accounts still answer on the old path.

    Docs: GET /integration/product/sellers/{sellerId}/products
    Flat response: each content item carries barcode, title, stockCode,
    quantity, salePrice and an `images` list of {"url": ...} entries.
    """
    params = {"page": page, "size": size}
    if approved is not None:
        params["approved"] = str(approved).lower()
    if archived is not None:
        params["archived"] = str(archived).lower()
    if on_sale is not None:
        params["onSale"] = str(on_sale).lower()

    url = f"{BASE_URL}/product/sellers/{SUPPLIER_ID}/products"
    resp = requests.get(url, headers=_auth_header(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def iter_all_products(size=100, status=None):
    """Yield (api_version, product) for every product, paging all the way
    through. Tries V2 first and falls back to V1 if this seller's account
    still only answers on the old endpoint."""
    use_v1 = False
    try:
        first = get_approved_products(page=0, size=size, status=status)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (400, 404, 410):
            use_v1 = True
            first = get_products_v1(page=0, size=size)
        else:
            raise

    version = "v1" if use_v1 else "v2"
    fetch = (lambda p: get_products_v1(page=p, size=size)) if use_v1 else (
        lambda p: get_approved_products(page=p, size=size, status=status)
    )

    data = first
    page = 0
    while True:
        content = data.get("content") or []
        for item in content:
            yield version, item

        total_pages = data.get("totalPages", 0)
        page += 1
        if page >= total_pages or not content:
            break
        data = fetch(page)


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
