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
from datetime import datetime, timezone
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


def get_shipped_packages(offset=0, limit=100):
    """Kargoya verilmiş paketler (OMS /packages/.../shipped).
    Canlı ortamda test edildi: {"totalCount", "limit", "offset", "pageCount", "items"}."""
    url = f"{OMS_BASE}/packages/merchantid/{MERCHANT_ID}/shipped"
    return _request("GET", url, params={"offset": offset, "limit": limit})


def get_unpacked_packages(offset=0, limit=100):
    """Paketlenmemiş kalemler (OMS /packages/.../status/unpacked)."""
    url = f"{OMS_BASE}/packages/merchantid/{MERCHANT_ID}/status/unpacked"
    return _request("GET", url, params={"offset": offset, "limit": limit})


def get_order_detail(order_number):
    """Tek bir siparişin detayı."""
    url = f"{OMS_BASE}/orders/merchantid/{MERCHANT_ID}/ordernumber/{order_number}"
    return _request("GET", url)


# --- Sipariş işleme (yazma) -------------------------------------------------
# Gövde şemaları Hepsiburada'nın açık kaynak PHP SDK'sından alındı ve SIT
# ortamında doğrulandı: geçersiz bir lineItemId ile denendiğinde API artık
# genel "Line items empty or null" yerine "lineItemId is not valid ..."
# döndürüyor; yani gövde doğru ayrıştırılıyor.

def create_package(line_items, parcel_quantity=1, deci=1):
    """Sipariş kalemlerini paketler.

    line_items: [{"id": "<lineItemId GUID>", "quantity": 1}, ...]
    Döndürdüğü yanıtta oluşan paket numarası bulunur."""
    url = f"{OMS_BASE}/packages/merchantid/{MERCHANT_ID}"
    body = {
        "parcelQuantity": parcel_quantity,
        "deci": deci,
        "lineItemRequests": line_items,
    }
    return _request("POST", url, json=body)


def unpack_package(package_number):
    """Paketi bozar (kalemleri paketlenmemiş durumuna döndürür)."""
    url = f"{OMS_BASE}/packages/merchantid/{MERCHANT_ID}/packagenumber/{package_number}/unpack"
    return _request("POST", url)


def send_invoice(package_number, invoice_link):
    """Pakete fatura bağlantısı iletir (PUT)."""
    url = f"{OMS_BASE}/packages/merchantid/{MERCHANT_ID}/packagenumber/{package_number}/invoice"
    return _request("PUT", url, json={"invoiceLink": invoice_link})


def get_cargo_label(package_number, fmt="pdf"):
    """Kargo barkodu/etiketi."""
    url = f"{OMS_BASE}/packages/merchantid/{MERCHANT_ID}/packagenumber/{package_number}/label"
    return _request("GET", url, params={"format": fmt})


def send_delivered_status(package_number, received_by, received_date=None):
    """Teslim edildi bilgisini iletir.

    received_date: "2026-08-15T11:30:30.230Z" biçiminde; verilmezse şu an."""
    if received_date is None:
        received_date = (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") +
            f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"
        )
    url = f"{OMS_BASE}/packages/merchantid/{MERCHANT_ID}/packagenumber/{package_number}/deliver"
    body = {"receivedDate": received_date, "receivedBy": received_by}
    return _request("POST", url, json=body)


def cancel_line_item(line_item_id, reason_id):
    """Satıcı kaynaklı kalem iptali (tedarik edilemedi vb.)."""
    url = f"{OMS_BASE}/lineitems/merchantid/{MERCHANT_ID}/id/{line_item_id}/cancelbymerchant"
    return _request("POST", url, json={"reasonId": reason_id})


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
