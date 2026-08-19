"""Ortam değişkenlerini ve sabitleri tek yerden yönetir."""

import os

# --- Meta (Facebook + Instagram) ---
GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v23.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

META_TOKEN = os.environ.get("META_ACCESS_TOKEN", "").strip()
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "").strip()
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()

# --- Threads ---
# Threads kendi API'sini kullanıyor (graph.threads.net), Facebook Graph'tan
# ayrı bir token ister. tools/threads_auth.py ile üretilir.
THREADS_VERSION = os.environ.get("THREADS_API_VERSION", "v1.0")
THREADS_BASE = f"https://graph.threads.net/{THREADS_VERSION}"

THREADS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
THREADS_USER_ID = os.environ.get("THREADS_USER_ID", "").strip()
THREADS_APP_ID = os.environ.get("THREADS_APP_ID", "").strip()
THREADS_APP_SECRET = os.environ.get("THREADS_APP_SECRET", "").strip()

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
# GitHub Actions ve GitLab CI içinde otomatik dolar; yerelde elle verebilirsin.
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "").strip()  # "kullanici/repo"
GITHUB_BRANCH = os.environ.get("GITHUB_REF_NAME", "main").strip()

# GitLab CI bu üçünü kendisi tanımlar.
GITLAB_SERVER = os.environ.get("CI_SERVER_URL", "https://gitlab.com").strip()
GITLAB_PROJECT = os.environ.get("CI_PROJECT_PATH", "").strip()  # "kullanici/repo"
GITLAB_BRANCH = os.environ.get("CI_COMMIT_REF_NAME", "main").strip()

MEDIA_BASE_URL = os.environ.get("MEDIA_BASE_URL", "").strip()

# Otomatik üretilen taslakların varsayılan platformları. Bir platformu
# taslaklardan çıkarmak için ortam değişkenini değiştirmen yeter, örn.
# POST_PLATFORMS="instagram,facebook"
DEFAULT_PLATFORMS = [
    p.strip().lower()
    for p in os.environ.get("POST_PLATFORMS", "instagram,facebook,threads").split(",")
    if p.strip()
]

# --- Pinterest ---
# Resmî v5 API (src/pinterest.py) işletme hesabı + onaylı app ister; kullanıcı
# işletme hesabı olmayacağını söyledi, o yüzden fiilen pinterest_studio
# (arayüz otomasyonu, çerezle) kullanılıyor. API alanları ileride gerekirse diye
# duruyor — boş kalmaları sorun değil.
PINTEREST_BASE = os.environ.get("PINTEREST_API_BASE", "https://api.pinterest.com/v5").rstrip("/")
PINTEREST_APP_ID = os.environ.get("PINTEREST_APP_ID", "").strip()
PINTEREST_APP_SECRET = os.environ.get("PINTEREST_APP_SECRET", "").strip()
PINTEREST_REFRESH_TOKEN = os.environ.get("PINTEREST_REFRESH_TOKEN", "").strip()
PINTEREST_ACCESS_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()
# Pin'lerin gideceği varsayılan pano: ID ya da pano adı olabilir.
PINTEREST_BOARD_ID = os.environ.get("PINTEREST_BOARD_ID", "").strip()

# Kuru çalışma: API çağrısı yapmadan ne olacağını gösterir.
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in ("1", "true", "yes")

# Tek çalışmada en fazla kaç post paylaşılsın. Bot saat başı çalıştığı için
# birikmiş kuyruk saatlere yayılır; 0 yazarsan sınır kalkar.
try:
    MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "1"))
except ValueError:
    MAX_PER_RUN = 1


def media_url(relative_path: str) -> str:
    """posts/media/foo.jpg -> herkese açık https URL."""
    if relative_path.startswith("http://") or relative_path.startswith("https://"):
        return relative_path

    rel = relative_path.lstrip("/")

    if MEDIA_BASE_URL:
        return f"{MEDIA_BASE_URL.rstrip('/')}/{rel}"

    if GITHUB_REPO:
        return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{rel}"

    if GITLAB_PROJECT:
        # GitLab raw, PUBLIC projelerde görselleri doğru content-type ile sunuyor.
        # Proje private ise bu adres çalışmaz — o durumda MEDIA_BASE_URL tanımla.
        return f"{GITLAB_SERVER.rstrip('/')}/{GITLAB_PROJECT}/-/raw/{GITLAB_BRANCH}/{rel}"

    raise RuntimeError(
        "Medya URL'i kurulamadı. MEDIA_BASE_URL, GITHUB_REPOSITORY "
        "ya da CI_PROJECT_PATH tanımlı olmalı."
    )
