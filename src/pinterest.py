"""Pinterest API v5 ile pin paylaşımı.

Pinterest bir pin'i üç parçadan kurar: görsel, başlık/açıklama ve tıklanınca
gidilecek bağlantı. Post dosyalarımızda başlık ayrı durmadığı için metnin ilk
satırı başlık, tamamı açıklama, içindeki ilk https adresi de bağlantı olarak
kullanılır. İstersen front matter'da elle de verebilirsin:

    ---
    platforms: [pinterest]
    media: posts/media/urun.jpg
    pinterest_board: Elektronik Setler   # ad ya da ID; boşsa PINTEREST_BOARD_ID
    baslik: Arduino Başlangıç Seti
    link: https://atolyeelektronik.com/products/arduino-baslangic-seti
    ---

Yetkilendirme `tools/pinterest_auth.py` ile bir kez yapılır; sonrasında
refresh token'dan her çalışmada yeni access token alınır.
"""

from __future__ import annotations

import base64
import pathlib
import re
import time

import requests

from . import config

# Pinterest sınırları
TITLE_MAX = 100
DESCRIPTION_MAX = 800
ALT_TEXT_MAX = 500
CAROUSEL_MAX = 5  # karusel pin en fazla 5 görsel alır

URL_RE = re.compile(r"https?://\S+")


class PinterestError(RuntimeError):
    pass


# --- Yetkilendirme -----------------------------------------------------------

def get_access_token() -> str:
    """Elde hazır access token varsa onu, yoksa refresh token'dan yenisini verir."""
    if config.PINTEREST_ACCESS_TOKEN:
        return config.PINTEREST_ACCESS_TOKEN

    if not (config.PINTEREST_APP_ID and config.PINTEREST_APP_SECRET):
        raise PinterestError("PINTEREST_APP_ID / PINTEREST_APP_SECRET tanımlı değil.")
    if not config.PINTEREST_REFRESH_TOKEN:
        raise PinterestError(
            "PINTEREST_REFRESH_TOKEN tanımlı değil. "
            "tools/pinterest_auth.py çalıştırıp üretebilirsin."
        )

    basic = base64.b64encode(
        f"{config.PINTEREST_APP_ID}:{config.PINTEREST_APP_SECRET}".encode()
    ).decode()

    response = requests.post(
        f"{config.PINTEREST_BASE}/oauth/token",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": config.PINTEREST_REFRESH_TOKEN,
        },
        timeout=60,
    )
    payload = response.json()
    if "access_token" not in payload:
        raise PinterestError(f"Access token alınamadı: {payload}")
    return payload["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _check(response: requests.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        raise PinterestError(f"HTTP {response.status_code}: {response.text[:300]}") from None
    if response.status_code >= 400:
        mesaj = payload.get("message") or payload.get("error_description") or payload
        raise PinterestError(f"HTTP {response.status_code}: {mesaj}")
    return payload


# --- Pano (board) ------------------------------------------------------------

def list_boards(token: str | None = None) -> list[dict]:
    token = token or get_access_token()
    response = requests.get(
        f"{config.PINTEREST_BASE}/boards",
        headers={"Authorization": f"Bearer {token}"},
        params={"page_size": 100},
        timeout=60,
    )
    return _check(response).get("items", [])


def resolve_board(board: str, token: str) -> str:
    """Pano adını ID'ye çevirir. Zaten ID verilmişse dokunmaz."""
    board = board.strip()
    if board.isdigit():
        return board

    boards = list_boards(token)
    for item in boards:
        if item.get("name", "").strip().lower() == board.lower():
            return str(item["id"])

    adlar = ", ".join(b.get("name", "?") for b in boards) or "(hiç pano yok)"
    raise PinterestError(f"'{board}' adında pano bulunamadı. Mevcut panolar: {adlar}")


# --- Metin parçalama ---------------------------------------------------------

def title_from(caption: str, extra: dict) -> str:
    title = (extra.get("baslik") or extra.get("title") or "").strip()
    if not title:
        for line in caption.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                title = line
                break
    return title[:TITLE_MAX]


def description_from(caption: str) -> str:
    """Pin açıklamasını hazırlar.

    Carousel'e özel satırlar ("Cevabı carousel'de 👉 kaydır" gibi) tek
    görselli bir pinde anlamsız kalıyor — TikTok tarafında olduğu gibi
    burada da ayıklanıyor.
    """
    satirlar = [
        s for s in caption.splitlines()
        if "carousel" not in s.lower() and "kaydır" not in s.lower()
    ]
    return "\n".join(satirlar).strip()[:DESCRIPTION_MAX]


def link_from(caption: str, extra: dict) -> str | None:
    link = (extra.get("link") or extra.get("url") or "").strip()
    if link:
        return link
    match = URL_RE.search(caption)
    return match.group(0).rstrip(".,)") if match else None


# --- Video yükleme -----------------------------------------------------------

def _upload_video(token: str, video_path: str) -> str:
    """Videoyu Pinterest'in yükleme adresine gönderir, media_id döndürür."""
    path = pathlib.Path(video_path)
    if not path.exists():
        raise PinterestError(
            f"Video dosyası bulunamadı: {video_path} — Pinterest video pin'i için "
            "dosyanın repoda yerel olarak durması gerekiyor (URL yetmiyor)."
        )

    kayit = _check(
        requests.post(
            f"{config.PINTEREST_BASE}/media",
            headers=_headers(token),
            json={"media_type": "video"},
            timeout=60,
        )
    )
    media_id = str(kayit["media_id"])
    upload_url = kayit["upload_url"]
    fields = kayit.get("upload_parameters") or {}

    # Alanlar dosyadan ÖNCE gelmeli — S3 form yüklemesi bunu şart koşuyor.
    with path.open("rb") as handle:
        files = [(key, (None, value)) for key, value in fields.items()]
        files.append(("file", (path.name, handle, "video/mp4")))
        response = requests.post(upload_url, files=files, timeout=600)
    if response.status_code >= 400:
        raise PinterestError(f"Video yüklenemedi (HTTP {response.status_code}).")

    return _wait_for_media(token, media_id)


def _wait_for_media(token: str, media_id: str, timeout_seconds: int = 600) -> str:
    deadline = time.time() + timeout_seconds
    son = ""
    while time.time() < deadline:
        durum = _check(
            requests.get(
                f"{config.PINTEREST_BASE}/media/{media_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=60,
            )
        )
        son = durum.get("status", "")
        if son == "succeeded":
            return media_id
        if son == "failed":
            raise PinterestError("Pinterest videoyu işleyemedi.")
        time.sleep(10)
    raise PinterestError(f"Video işleme zaman aşımına uğradı (son durum: {son}).")


# --- Yayınlama ---------------------------------------------------------------

def _media_source(media_paths: list[str], is_video: bool, token: str, extra: dict) -> dict:
    if is_video:
        kapak = (extra.get("kapak") or extra.get("cover") or "").strip()
        if not kapak:
            raise PinterestError(
                "Pinterest video pin'i bir kapak görseli ister. Post dosyasına "
                "'kapak: posts/media/....jpg' satırı ekle."
            )
        media_id = _upload_video(token, media_paths[0])
        return {
            "source_type": "video_id",
            "media_id": media_id,
            "cover_image_url": config.media_url(kapak),
        }

    urls = [config.media_url(p) for p in media_paths]
    if len(urls) == 1:
        return {"source_type": "image_url", "url": urls[0]}

    if len(urls) > CAROUSEL_MAX:
        print(f"  (Pinterest en fazla {CAROUSEL_MAX} görsel kabul ediyor, fazlası atlandı)")
        urls = urls[:CAROUSEL_MAX]
    return {
        "source_type": "multiple_image_urls",
        "items": [{"url": url} for url in urls],
        "index": 0,
    }


def publish(
    caption: str,
    media_path: str | list[str] | None,
    is_video: bool = False,
    extra: dict | None = None,
) -> str:
    extra = extra or {}

    if not media_path:
        raise PinterestError("Pinterest için post dosyasına 'media:' satırı ekle.")

    board = (extra.get("pinterest_board") or config.PINTEREST_BOARD_ID or "").strip()
    if not board:
        raise PinterestError(
            "PINTEREST_BOARD_ID tanımlı değil (ya da post dosyasında "
            "'pinterest_board:' satırı yok)."
        )

    media_paths = media_path if isinstance(media_path, list) else [media_path]
    title = title_from(caption, extra)
    link = link_from(caption, extra)

    if config.DRY_RUN:
        for p in media_paths[:CAROUSEL_MAX]:
            print(f"  [DRY RUN] Pinterest ← {config.media_url(p)}")
        print(f"  [DRY RUN] pano: {board} | başlık: {title!r} | bağlantı: {link}")
        return "dry-run"

    token = get_access_token()

    body = {
        "board_id": resolve_board(board, token),
        "title": title,
        "description": description_from(caption),
        "alt_text": title[:ALT_TEXT_MAX],
        "media_source": _media_source(media_paths, is_video, token, extra),
    }
    if link:
        body["link"] = link

    created = _check(
        requests.post(
            f"{config.PINTEREST_BASE}/pins",
            headers=_headers(token),
            json=body,
            timeout=180,
        )
    )
    return str(created.get("id", ""))


def main() -> None:
    """`python -m src.pinterest` — bağlantıyı ve panoları kontrol eder."""
    token = get_access_token()
    hesap = _check(
        requests.get(
            f"{config.PINTEREST_BASE}/user_account",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
    )
    print(f"✅ Bağlantı tamam — hesap: {hesap.get('username')} ({hesap.get('account_type')})")
    print("\nPanolar:")
    for board in list_boards(token):
        print(f"  {board['id']}  {board.get('name')}")
    print("\nKullanmak istediğin panonun ID'sini PINTEREST_BOARD_ID olarak tanımla.")


if __name__ == "__main__":
    main()
