"""TikTok Content Posting API ile video paylaşımı.

Akış:
  1. Refresh token ile taze bir access token al
  2. creator_info/query → hesabın izin verdiği gizlilik seçeneklerini öğren
  3. video/init/ → yükleme adresi al (FILE_UPLOAD yöntemi)
  4. Videoyu o adrese yükle
  5. status/fetch/ → sonucu sorgula

Not: Uygulama TikTok denetiminden (audit) geçene kadar paylaşımlar
zorunlu olarak SELF_ONLY (sadece sen görebilirsin) olarak yayınlanır.
"""

from __future__ import annotations

import os
import time

import requests

from . import config

API = "https://open.tiktokapis.com/v2"


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
        raise TikTokError("TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET tanımlı değil.")
    if not config.TIKTOK_REFRESH_TOKEN:
        raise TikTokError(
            "TIKTOK_REFRESH_TOKEN tanımlı değil. "
            "Önce tools/tiktok_auth.py ile bir kerelik yetkilendirme yap."
        )

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
        raise TikTokError(f"Access token alınamadı: {payload}")

    new_refresh = payload.get("refresh_token")
    if new_refresh and new_refresh != config.TIKTOK_REFRESH_TOKEN:
        # TikTok refresh token'ı döndürebiliyor. Yeni değeri log'a basmıyoruz
        # ama kullanıcıyı uyarıyoruz.
        print(
            "  [uyarı] TikTok yeni bir refresh token verdi. "
            "Paylaşımlar bir süre sonra durursa yetkilendirmeyi tekrarla."
        )

    return payload["access_token"]


def _creator_info(token: str) -> dict:
    response = requests.post(
        f"{API}/post/publish/creator_info/query/",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        timeout=60,
    )
    return _check(response.json()).get("data", {})


def _wait_for_status(token: str, publish_id: str, timeout_seconds: int = 300) -> dict:
    deadline = time.time() + timeout_seconds
    last: dict = {}
    while time.time() < deadline:
        response = requests.post(
            f"{API}/post/publish/status/fetch/",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json={"publish_id": publish_id},
            timeout=60,
        )
        last = _check(response.json()).get("data", {})
        status = last.get("status")
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            return last
        if status == "FAILED":
            raise TikTokError(f"Paylaşım başarısız: {last}")
        time.sleep(5)
    return last


def publish(caption: str, media_path: str | None, is_video: bool = True) -> str:
    if not media_path:
        raise TikTokError("TikTok sadece video paylaşımına izin veriyor.")
    if not is_video:
        raise TikTokError("TikTok için 'media' bir video dosyası olmalı (.mp4).")

    local_path = media_path
    if not os.path.exists(local_path):
        raise TikTokError(f"Video dosyası bulunamadı: {local_path}")

    file_size = os.path.getsize(local_path)

    if config.DRY_RUN:
        print(f"  [DRY RUN] TikTok → {local_path} ({file_size} bayt)")
        return "dry-run"

    token = get_access_token()

    info = _creator_info(token)
    allowed = info.get("privacy_level_options") or []
    privacy = "SELF_ONLY" if "SELF_ONLY" in allowed or not allowed else allowed[0]

    init = requests.post(
        f"{API}/post/publish/video/init/",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
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
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        },
        timeout=60,
    )
    data = _check(init.json()).get("data", {})
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")
    if not (publish_id and upload_url):
        raise TikTokError(f"Yükleme başlatılamadı: {data}")

    with open(local_path, "rb") as handle:
        upload = requests.put(
            upload_url,
            headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(file_size),
                "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            },
            data=handle,
            timeout=600,
        )
    if upload.status_code not in (200, 201, 204):
        raise TikTokError(f"Video yüklenemedi (HTTP {upload.status_code}).")

    result = _wait_for_status(token, publish_id)
    print(f"  TikTok durumu: {result.get('status')} (gizlilik: {privacy})")
    return publish_id
