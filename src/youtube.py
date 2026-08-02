"""YouTube Data API v3 ile video yukleme (Shorts dahil).

Dikey ve 3 dakikadan kisa videolar YouTube tarafindan otomatik olarak
Shorts sayilir; ayri bir ayar gerekmiyor.

Gerekli GitHub Secrets:
  YOUTUBE_CLIENT_ID
  YOUTUBE_CLIENT_SECRET
  YOUTUBE_REFRESH_TOKEN   (tools/youtube_auth.py ile bir kerelik uretilir)

Istege bagli post alanlari (post dosyasinin front matter kismi):
  youtube_privacy: public | unlisted | private   (varsayilan: public)
  youtube_title:   ozel baslik (varsayilan: metnin ilk satiri)
"""

from __future__ import annotations

import os
import re

import requests

from . import config

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

DEFAULT_PRIVACY = os.environ.get("YOUTUBE_PRIVACY", "public").strip() or "public"


class YouTubeError(RuntimeError):
    pass


def get_access_token() -> str:
    if not (CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN):
        raise YouTubeError(
            "YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN tanimli degil."
        )
    r = requests.post(
        TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=60,
    )
    payload = r.json()
    if "access_token" not in payload:
        raise YouTubeError(f"Access token alinamadi: {payload}")
    return payload["access_token"]


def _split_caption(caption: str) -> tuple[str, str, list[str]]:
    """Metni baslik, aciklama ve etiketlere ayirir."""
    lines = [ln.strip() for ln in caption.strip().splitlines()]
    title = next((ln for ln in lines if ln), "Atolye Elektronik")
    title = re.sub(r"#\w+", "", title).strip(" -–—•")[:95] or "Atolye Elektronik"
    tags = [t.lstrip("#") for t in re.findall(r"#\w+", caption)][:15]
    return title, caption.strip(), tags


def publish(caption: str, media_path: str | None, is_video: bool = True, extra: dict | None = None) -> str:
    if not media_path:
        raise YouTubeError("YouTube sadece video yuklemesine izin veriyor.")
    if not is_video:
        raise YouTubeError("YouTube icin 'media' bir video dosyasi olmali (.mp4).")
    if not os.path.exists(media_path):
        raise YouTubeError(f"Video dosyasi bulunamadi: {media_path}")

    extra = extra or {}
    size = os.path.getsize(media_path)
    title, description, tags = _split_caption(caption)
    title = (extra.get("youtube_title") or title)[:95]
    privacy = (extra.get("youtube_privacy") or DEFAULT_PRIVACY).lower()
    if privacy not in ("public", "unlisted", "private"):
        privacy = "public"

    if config.DRY_RUN:
        print(f"  [DRY RUN] YouTube → {media_path} ({size} bayt)")
        print(f"  [DRY RUN] baslik: {title} | gizlilik: {privacy} | etiket: {len(tags)}")
        return "dry-run"

    token = get_access_token()

    meta = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    start = requests.post(
        UPLOAD_URL,
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(size),
            "X-Upload-Content-Type": "video/mp4",
        },
        json=meta,
        timeout=60,
    )
    if start.status_code not in (200, 201):
        raise YouTubeError(f"Yukleme baslatilamadi (HTTP {start.status_code}): {start.text[:300]}")

    session_url = start.headers.get("Location")
    if not session_url:
        raise YouTubeError("Yukleme adresi alinamadi.")

    with open(media_path, "rb") as handle:
        put = requests.put(
            session_url,
            headers={"Content-Type": "video/mp4", "Content-Length": str(size)},
            data=handle,
            timeout=1800,
        )
    if put.status_code not in (200, 201):
        raise YouTubeError(f"Video yuklenemedi (HTTP {put.status_code}): {put.text[:300]}")

    video_id = put.json().get("id", "")
    print(f"  YouTube: https://youtu.be/{video_id} (gizlilik: {privacy})")
    return video_id
