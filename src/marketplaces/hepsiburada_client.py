"""
Hepsiburada Marketplace API client — order fetch + price/stock update.

Auth model (Hepsiburada entegrasyon ekibinin ilettiği bilgilere göre):
- Basic Authentication: username = MerchantId (GUID), password = SecretKey
- User-Agent header: geliştirici kullanıcı adı (ör. "atolyeelektronik_dev")
  — bu header girilmezse API 403 döner.

Endpoints:
- Orders/OMS:  https://oms-external.hepsiburada.com      (test: oms-external-sit)
- Listings:    https://listing-external.hepsiburada.com  (test: listing-external-sit)
Docs: https://developers.hepsiburada.com

Credentials come from environment variables (set as GitHub Actions secrets
in CI, or a local .env file for testing on your own machine):
    HEPSIBURADA_MERCHANT_ID    (GUID — Basic auth kullanıcı adı olarak da kullanılır)
    HEPSIBURADA_SECRET_KEY     (Basic auth şifresi)
    HEPSIBURADA_DEV_USERNAME   (User-Agent header'ına yazılan geliştirici adı)
    HEPSIBURADA_ENV            (opsiyonel: "sit" test ortamı, varsayılan "prod")
"""

import os
from pathlib import Path

import requests


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

MERCHANT_ID = os.environ.get("HEPSIBURADA_MERCHANT_ID")
SECRET_KEY = os.environ.get("HEPSIBURADA_SECRET_KEY")
DEV_USERNAME = os.environ.get("HEPSIBURADA_DEV_USERNAME")
ENV = os.environ.get("HEPSIBURADA_ENV", "prod").lower()

if ENV == "sit":
    OMS_BASE = "https://oms-external-sit.hepsiburada.com"
    LISTING_BASE = "https://listing-external-sit.hepsiburada.com"
else:
    OMS_BASE = "https://oms-external.hepsiburada.com"
    LISTING_BASE = "https://listing-external.hepsiburada.com"


def _check_config():
    missing = [
        name
        for name, val in [
            ("HEPSIBURADA_MERCHANT_ID", MERCHANT_ID),
            ("HEPSIBURADA_SECRET_KEY", SECRET_KEY),
            ("HEPSIBURADA_DEV_USERNAME", DEV_USERNAME),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            "Eksik ortam değişkeni(leri): " + ", ".join(missing) +
            " — GitHub Actions Secrets veya yerel .env dosyasını kontrol et."
        )


def _request(method, url, **kwargs):
    _check_config()
    headers = {
        "User-Agent": DEV_USERNAME,  # zorunlu, yoksa 403
        "Accept": "application/json",
    }
    if method != "GET":
        headers["Content-Type"] = "application/json"
    resp = requests.request(
        method, url, headers=headers, auth=(MERCHANT_ID, SECRET_KEY), timeout=30, **kwargs
    )
    resp.raise_for_status()
    if not resp.content:
        return {}
    return resp.json()


def get_new_order_items(offset=0, limit=100):
    """Paketlenmemiş yeni sipariş kalemleri (OMS /orders)."""
    url = f"{OMS_BASE}/orders/merchantid/{MERCHANT_ID}"
    return _request("GET", url, params={"offset": offset, "limit": limit})


def get_packages(offset=0, limit=100):
    """Paketlenmiş, kargoya verilmeyi bekleyen paketler (OMS /packages)."""
    url = f"{OMS_BASE}/packages/merchantid/{MERCHANT_ID}"
    return _request("GET", url, params={"offset": offset, "limit": limit})


def get_listings(offset=0, limit=100):
    """Mağazadaki listing'ler (hepsiburadaSku/merchantSku eşlemesi için)."""
    url = f"{LISTING_BASE}/listings/merchantid/{MERCHANT_ID}"
    return _request("GET", url, params={"offset": offset, "limit": limit})


def update_stock(items):
    """items: list of {"hepsiburadaSku": str, "merchantSku": str, "availableStock": int}
    Returns upload info with an "id" to check via get_stock_upload_status()."""
    url = f"{LISTING_BASE}/listings/merchantid/{MERCHANT_ID}/stock-uploads"
    return _request("POST", url, json=items)


def update_price(items):
    """items: list of {"hepsiburadaSku": str, "merchantSku": str, "price": float}
    Returns upload info with an "id" to check via get_price_upload_status()."""
    url = f"{LISTING_BASE}/listings/merchantid/{MERCHANT_ID}/price-uploads"
    return _request("POST", url, json=items)


def get_stock_upload_status(upload_id):
    url = f"{LISTING_BASE}/listings/merchantid/{MERCHANT_ID}/stock-uploads/id/{upload_id}"
    return _request("GET", url)


def get_price_upload_status(upload_id):
    url = f"{LISTING_BASE}/listings/merchantid/{MERCHANT_ID}/price-uploads/id/{upload_id}"
    return _request("GET", url)
