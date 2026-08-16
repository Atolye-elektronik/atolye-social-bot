"""
Hepsiburada MPOP (katalog) API istemcisi — kategori sorgulama + ürün oluşturma.

hepsiburada_client.py sipariş (OMS) ve fiyat/stok (listing) tarafını kapsıyor;
bu dosya ise **yeni ürün açma** tarafını ekler. Ayrı bir dosya olmasının sebebi
farklı bir alan adı (mpop) ve çoğu satıcıda farklı bir kullanıcı adı/şifre
çifti kullanılması.

Endpoint'ler (Hepsiburada PHP SDK'sının Endpoints.php dosyasından doğrulandı —
github.com/mustafa-m-ugur/hepsiburada-api-php):
    GET  /product/api/categories/get-all-categories
    GET  /product/api/categories/{categoryId}/attributes
    GET  /product/api/categories/{categoryId}/attribute/{attributeSlug}/values
    POST /product/api/products/import          -> ürün oluşturma
    POST /product/api/products/fastlisting     -> katalogda barkodu olan ürünü listeleme
    GET  /product/api/products/status/{trackingId}

Kimlik bilgileri (ortam değişkeni / GitHub Secret):
    HEPSIBURADA_MPOP_USERNAME  (yoksa HEPSIBURADA_DEV_USERNAME kullanılır)
    HEPSIBURADA_MPOP_PASSWORD  (yoksa HEPSIBURADA_SECRET_KEY kullanılır)
    HEPSIBURADA_MERCHANT_ID
    HEPSIBURADA_ENV            ("sit" test ortamı, varsayılan "prod")

DİKKAT: MPOP'un Basic auth kullanıcı adı çoğu satıcıda merchantId GUID'i DEĞİL,
entegrasyon panelindeki geliştirici kullanıcı adıdır (ör. "atolyeelektronik_dev").
403 alırsan önce bunu kontrol et.
"""

import json
import os
from pathlib import Path

import requests

try:
    from hepsiburada_client import _load_dotenv
except ImportError:  # paket olarak import edildiğinde
    from .hepsiburada_client import _load_dotenv

_load_dotenv()

MERCHANT_ID = os.environ.get("HEPSIBURADA_MERCHANT_ID")
DEV_USERNAME = os.environ.get("HEPSIBURADA_DEV_USERNAME")
# Basic auth kullanıcı adı MerchantId'nin kendisi (entegrasyon ekibinin
# ilettiği bilgiye göre) — geliştirici kullanıcı adı değil, o User-Agent'a
# giriyor. Farklı bir MPOP kullanıcısı verilirse o öne geçer.
USERNAME = os.environ.get("HEPSIBURADA_MPOP_USERNAME") or MERCHANT_ID
PASSWORD = os.environ.get("HEPSIBURADA_MPOP_PASSWORD") or os.environ.get(
    "HEPSIBURADA_SECRET_KEY"
)
ENV = os.environ.get("HEPSIBURADA_ENV", "prod").lower()

MPOP_BASE = (
    "https://mpop-sit.hepsiburada.com" if ENV == "sit" else "https://mpop.hepsiburada.com"
)


def _check_config():
    missing = [
        name
        for name, val in [
            ("HEPSIBURADA_MERCHANT_ID", MERCHANT_ID),
            ("HEPSIBURADA_DEV_USERNAME", DEV_USERNAME),
            ("HEPSIBURADA_MPOP_PASSWORD / HEPSIBURADA_SECRET_KEY", PASSWORD),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            "Eksik ortam değişkeni(leri): " + ", ".join(missing) +
            " — GitHub Actions Secrets veya yerel .env dosyasını kontrol et."
        )


def _request(method, path, **kwargs):
    _check_config()
    headers = {
        # OMS tarafında olduğu gibi burada da User-Agent zorunlu; boş bırakılırsa 403.
        # Buraya geliştirici kullanıcı adı giriyor (ör. "atolyeelektronik_dev").
        "User-Agent": DEV_USERNAME,
        "Accept": "application/json",
    }
    headers.update(kwargs.pop("headers", {}))
    resp = requests.request(
        method,
        f"{MPOP_BASE}{path}",
        headers=headers,
        auth=(USERNAME, PASSWORD),
        timeout=60,
        **kwargs,
    )
    resp.raise_for_status()
    return resp.json() if resp.content else {}


# --- Kategori -------------------------------------------------------------

def get_categories(page=0, size=500, leaf=True, status="ACTIVE", available=True):
    """Kategori ağacı. Ürün ancak leaf=true ve available=true olan bir
    kategoriye açılabilir."""
    params = {
        "page": page,
        "size": size,
        "leaf": str(leaf).lower(),
        "status": status,
        "available": str(available).lower(),
    }
    return _request("GET", "/product/api/categories/get-all-categories", params=params)


def search_categories(kelime, max_page=10):
    """Kategori adında kelime geçenleri döndürür — categoryId bulmak için.

    Hepsiburada'nın kategori listesi binlerce satır; sayfa sayfa gezip
    yerelde filtreliyoruz."""
    kelime = kelime.casefold()
    bulunan = []
    for page in range(max_page):
        data = get_categories(page=page)
        items = data.get("data") or data.get("categories") or []
        if not items:
            break
        for cat in items:
            ad = (cat.get("name") or "") + " " + (cat.get("displayName") or "")
            if kelime in ad.casefold():
                bulunan.append(cat)
        if len(items) < 500:
            break
    return bulunan


def get_category_attributes(category_id):
    """Kategorinin zorunlu + opsiyonel özellikleri."""
    return _request("GET", f"/product/api/categories/{category_id}/attributes")


def get_attribute_values(category_id, attribute_slug):
    """Seçenekli (enum) bir özelliğin alabileceği değerler."""
    return _request(
        "GET",
        f"/product/api/categories/{category_id}/attribute/{attribute_slug}/values",
    )


def zorunlu_ozellikler(category_id):
    """get_category_attributes çıktısından sadece zorunlu alanların slug listesi."""
    data = get_category_attributes(category_id)
    attrs = data.get("data", {}).get("baseAttributes", []) if isinstance(data, dict) else []
    attrs += data.get("data", {}).get("attributes", []) if isinstance(data, dict) else []
    return [a.get("id") or a.get("name") for a in attrs if a.get("mandatory")]


# --- Ürün oluşturma -------------------------------------------------------

def create_products(urunler, multipart=True):
    """Yeni ürün(ler) açar. Dönen yanıttaki trackingId ile durum sorgulanır.

    urunler: [{"categoryId": int, "merchant": "<merchantId>",
               "attributes": {"merchantSku": ..., "Barcode": ..., ...}}, ...]

    Bu uç form-data içinde .json dosyası bekliyor — SIT ortamında doğrulandı
    (2026-08-16): düz JSON gövde 500 döndürüyor, multipart ise trackingId ile
    başarılı yanıt veriyor. Bazı üçüncü parti SDK'lar düz JSON gönderiyor,
    o yol çalışmıyor; multipart=False sadece karşılaştırma için duruyor.
    """
    if multipart:
        files = {
            "file": (
                "products.json",
                json.dumps(urunler, ensure_ascii=False).encode("utf-8"),
                "application/json",
            )
        }
        return _request("POST", "/product/api/products/import", files=files)

    return _request(
        "POST",
        "/product/api/products/import",
        json=urunler,
        headers={"Content-Type": "application/json"},
    )


def fast_listing(urunler):
    """Hepsiburada katalogunda barkodu zaten kayıtlı ürünleri hızlıca listeler.
    Katalogda olmayan ürünler bu uçla açılmaz — create_products kullan."""
    return _request(
        "POST",
        "/product/api/products/fastlisting",
        json=urunler,
        headers={"Content-Type": "application/json"},
    )


def get_import_status(tracking_id):
    """create_products'ın döndürdüğü trackingId ile işlem sonucunu sorgular."""
    return _request("GET", f"/product/api/products/status/{tracking_id}")


def get_products_by_status(status="WAITING", page=0, size=100):
    """Mağazadaki ürünleri statüye göre listeler (WAITING, APPROVED, REJECTED...)."""
    params = {
        "merchantId": MERCHANT_ID,
        "productStatus": status,
        "page": page,
        "size": size,
    }
    return _request("GET", "/product/api/products/products-by-merchant-and-status", params=params)
