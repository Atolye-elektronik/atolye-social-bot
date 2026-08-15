"""Ortam değişkenlerini ve sabitleri tek yerden yönetir."""

import os

# --- Meta (Facebook + Instagram) ---
GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v23.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

META_TOKEN = os.environ.get("META_ACCESS_TOKEN", "").strip()
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "").strip()
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()

# --- TikTok ---
TIKTOK_CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
TIKTOK_CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
TIKTOK_REFRESH_TOKEN = os.environ.get("TIKTOK_REFRESH_TOKEN", "").strip()

# --- Shopify (opsiyonel — ürünlerden otomatik post üretmek için) ---
SHOPIFY_STORE = os.environ.get("SHOPIFY_STORE", "").strip()  # ör. atolyeelektronik
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_ADMIN_TOKEN", "").strip()
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2025-07")

# --- Repo / medya ---
# Görsellerin herkese açık URL'ini kurmak için kullanılır.
# GitHub Actions içinde otomatik dolar; yerelde elle verebilirsin.
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "").strip()  # "kullanici/repo"
GITHUB_BRANCH = os.environ.get("GITHUB_REF_NAME", "main").strip()
MEDIA_BASE_URL = os.environ.get("MEDIA_BASE_URL", "").strip()

# Kuru çalışma: API çağrısı yapmadan ne olacağını gösterir.
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in ("1", "true", "yes")


def media_url(relative_path: str) -> str:
    """posts/media/foo.jpg -> herkese açık https URL."""
    if relative_path.startswith("http://") or relative_path.startswith("https://"):
        return relative_path

    rel = relative_path.lstrip("/")

    if MEDIA_BASE_URL:
        return f"{MEDIA_BASE_URL.rstrip('/')}/{rel}"

    if GITHUB_REPO:
        return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{rel}"

    raise RuntimeError(
        "Medya URL'i kurulamadı. MEDIA_BASE_URL ya da GITHUB_REPOSITORY tanımlı olmalı."
    )
