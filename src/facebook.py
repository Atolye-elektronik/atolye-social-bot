"""Facebook Page'e metin, görsel veya video paylaşımı."""

from __future__ import annotations

import requests

from . import config


class FacebookError(RuntimeError):
    pass


def _post(base: str, path: str, params: dict) -> dict:
    params = {**params, "access_token": config.META_TOKEN}
    response = requests.post(f"{base}/{path}", data=params, timeout=180)
    payload = response.json()
    if "error" in payload:
        raise FacebookError(payload["error"].get("message", str(payload["error"])))
    return payload


def publish(caption: str, media_path: str | None, is_video: bool = False) -> str:
    if not config.FB_PAGE_ID:
        raise FacebookError("FB_PAGE_ID tanımlı değil.")

    if config.DRY_RUN:
        target = config.media_url(media_path) if media_path else "(sadece metin)"
        print(f"  [DRY RUN] Facebook → {target}")
        return "dry-run"

    if not media_path:
        result = _post(
            config.GRAPH_BASE, f"{config.FB_PAGE_ID}/feed", {"message": caption}
        )
        return result["id"]

    url = config.media_url(media_path)

    if is_video:
        result = _post(
            f"https://graph-video.facebook.com/{config.GRAPH_VERSION}",
            f"{config.FB_PAGE_ID}/videos",
            {"file_url": url, "description": caption},
        )
        return result.get("id", "")

    result = _post(
        config.GRAPH_BASE,
        f"{config.FB_PAGE_ID}/photos",
        {"url": url, "caption": caption, "published": "true"},
    )
    return result.get("post_id") or result.get("id", "")
