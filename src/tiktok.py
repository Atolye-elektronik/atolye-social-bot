"""TikTok Content Posting API ile video gönderimi.

İki mod var:

  Taslak modu (varsayılan)  — video, TikTok uygulamandaki gelen kutusuna
      düşer; yayınlama kararını sen verirsin. Denetimden geçmemiş
      uygulamalar için kısıtlama yok.

  Doğrudan paylaşım         — video doğrudan profile yayınlanır. TikTok
      bunu yalnızca denetimden geçmiş uygulamalara (ya da gizli hesaplara)
      izin veriyor. Denetim onaylandıktan sonra TIKTOK_DIRECT_POST=true
      yaparak açabilirsin.
"""

from __future__ import annotations

import os
import time

import requests

from . import config

API = "https://open.tiktokapis.com/v2"

DIRECT_POST = os.environ.get("TIKTOK_DIRECT_POST", "false").lower() in ("1", "true", "yes")


class TikTokError(RuntimeError):
    pass


def _check(payload: dict) -> dict:
    error = payload.get("error") or {}
    code = error.get("code", "ok")
    if code not in ("ok", "", None):
        raise TikTokError(f"{code}: {error.get('message', '')}")
    return payload


def get_access_token() -> str:
    if not (config.TIKTOK_CLIENT_KEY and config.TIKTOK_CLIENT_SECRET):
        raise TikTokError("TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET tanimli degil.")
    if not config.TIKTOK_REFRESH_TOKEN:
        raise TikTokError("TIKTOK_REFRESH_TOKEN tanimli degil.")

    response = requests.post(
        f"{API}/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": config.TIKTOK_CLIENT_KEY,
            "client_secret": config.TIKTOK_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": config.TIKTOK_REFRESH_TOKEN,
        },
        timeout=60,
    )
    payload = response.json()
    if "access_token" not in payload:
        raise TikTokError(f"Access token alinamadi: {payload}")
    return payload["access_token"]


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=UTF-8",
    }


def _creator_info(token: str) -> dict:
    r = requests.post(f"{API}/post/publish/creator_info/query/", headers=_headers(token), timeout=60)
    return _check(r.json()).get("data", {})


def _wait_for_status(token: str, publish_id: str, timeout_seconds: int = 300) -> dict:
    deadline = time.time() + timeout_seconds
    last: dict = {}
    while time.time() < deadline:
        r = requests.post(
            f"{API}/post/publish/status/fetch/",
            headers=_headers(token),
            json={"publish_id": publish_id},
            timeout=60,
        )
        last = _check(r.json()).get("data", {})
        status = last.get("status")
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            return last
        if status == "FAILED":
            raise TikTokError(f"Gonderim basarisiz: {last}")
        time.sleep(5)
    return last


def _upload(upload_url: str, path: str, size: int) -> None:
    with open(path, "rb") as handle:
        r = requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(size),
                "Content-Range": f"bytes 0-{size - 1}/{size}",
            },
            data=handle,
            timeout=600,
        )
    if r.status_code not in (200, 201, 204):
        raise TikTokError(f"Video yuklenemedi (HTTP {r.status_code}).")


def _init_draft(token: str, size: int) -> dict:
    r = requests.post(
        f"{API}/post/publish/inbox/video/init/",
        headers=_headers(token),
        json={
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            }
        },
        timeout=60,
    )
    return _check(r.json()).get("data", {})


def _init_direct(token: str, caption: str, size: int) -> dict:
    info = _creator_info(token)
    allowed = info.get("privacy_level_options") or []
    privacy = "SELF_ONLY" if ("SELF_ONLY" in allowed or not allowed) else allowed[0]
    r = requests.post(
        f"{API}/post/publish/video/init/",
        headers=_headers(token),
        json={
            "post_info": {
                "title": caption[:2200],
                "privacy_level": privacy,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            },
        },
        timeout=60,
    )
    return _check(r.json()).get("data", {})


def publish(caption: str, media_path: str | None, is_video: bool = True) -> str:
    if not media_path:
        raise TikTokError("TikTok sadece video gonderimine izin veriyor.")
    if not is_video:
        raise TikTokError("TikTok icin 'media' bir video dosyasi olmali (.mp4).")
    if not os.path.exists(media_path):
        raise TikTokError(f"Video dosyasi bulunamadi: {media_path}")

    size = os.path.getsize(media_path)
    mode = "dogrudan paylasim" if DIRECT_POST else "taslak"

    if config.DRY_RUN:
        print(f"  [DRY RUN] TikTok ({mode}) → {media_path} ({size} bayt)")
        return "dry-run"

    token = get_access_token()
    data = _init_direct(token, caption, size) if DIRECT_POST else _init_draft(token, size)

    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")
    if not (publish_id and upload_url):
        raise TikTokError(f"Yukleme baslatilamadi: {data}")

    _upload(upload_url, media_path, size)
    result = _wait_for_status(token, publish_id)

    status = result.get("status")
    if not DIRECT_POST:
        print("  TikTok uygulamandaki bildirimlerden videoyu acip yayinlayabilirsin.")
    print(f"  TikTok durumu: {status} (mod: {mode})")
    return publish_id
