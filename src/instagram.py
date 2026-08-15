"""Instagram Graph API ile içerik paylaşımı."""

from __future__ import annotations

import time

import requests

from . import config


class InstagramError(RuntimeError):
    pass


def _post(path: str, params: dict) -> dict:
    params = {**params, "access_token": config.META_TOKEN}
    response = requests.post(f"{config.GRAPH_BASE}/{path}", data=params, timeout=120)
    payload = response.json()
    if "error" in payload:
        raise InstagramError(payload["error"].get("message", str(payload["error"])))
    return payload


def _get(path: str, params: dict) -> dict:
    params = {**params, "access_token": config.META_TOKEN}
    response = requests.get(f"{config.GRAPH_BASE}/{path}", params=params, timeout=60)
    payload = response.json()
    if "error" in payload:
        raise InstagramError(payload["error"].get("message", str(payload["error"])))
    return payload


def _wait_until_ready(creation_id: str, timeout_seconds: int = 300) -> None:
    deadline = time.time() + timeout_seconds
    last: dict = {}
    while time.time() < deadline:
        try:
            last = _get(creation_id, {"fields": "status_code,status"})
        except InstagramError:
            time.sleep(5)
            continue

        code = last.get("status_code")
        if code == "FINISHED":
            return
        if code == "ERROR":
            raise InstagramError(f"Medya islenemedi: {last.get('status')}")
        time.sleep(5)

    raise InstagramError(f"Medya isleme zaman asimina ugradi: {last}")


def _publish_container(creation_id: str) -> str:
    last_error: Exception | None = None
    for _ in range(6):
        try:
            published = _post(
                f"{config.IG_USER_ID}/media_publish", {"creation_id": creation_id}
            )
            return published["id"]
        except InstagramError as exc:
            message = str(exc).lower()
            if "not available" not in message and "not ready" not in message:
                raise
            last_error = exc
            print("  (medya henuz hazir degil, tekrar denenecek)")
            time.sleep(10)
    raise InstagramError(f"Yayinlanamadi: {last_error}")


def _publish_carousel(caption: str, media_paths: list[str]) -> str:
    """2-10 gorselden olusan carousel paylasimi.

    Once her gorsel icin bir alt kapsayici (is_carousel_item) acilir,
    hepsi hazir olunca CAROUSEL tipinde ana kapsayici yayinlanir.
    """
    if len(media_paths) > 10:
        print("  (Instagram en fazla 10 gorsel kabul ediyor, fazlasi atlandi)")
        media_paths = media_paths[:10]

    urls = [config.media_url(p) for p in media_paths]

    if config.DRY_RUN:
        for url in urls:
            print(f"  [DRY RUN] Instagram carousel ← {url}")
        return "dry-run"

    children: list[str] = []
    for url in urls:
        child = _post(
            f"{config.IG_USER_ID}/media",
            {"image_url": url, "is_carousel_item": "true"},
        )
        children.append(child["id"])

    for child_id in children:
        _wait_until_ready(child_id)

    container = _post(
        f"{config.IG_USER_ID}/media",
        {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "caption": caption,
        },
    )
    creation_id = container["id"]
    _wait_until_ready(creation_id)
    return _publish_container(creation_id)


def publish(caption: str, media_path: str | list[str] | None, is_video: bool = False) -> str:
    if not config.IG_USER_ID:
        raise InstagramError("IG_USER_ID tanimli degil.")
    if not media_path:
        raise InstagramError("Instagram icin post dosyasina 'media:' satiri ekle.")

    if isinstance(media_path, list):
        if len(media_path) == 1:
            media_path = media_path[0]
        else:
            return _publish_carousel(caption, media_path)

    url = config.media_url(media_path)

    if config.DRY_RUN:
        print(f"  [DRY RUN] Instagram → {url}")
        return "dry-run"

    if is_video:
        container = _post(
            f"{config.IG_USER_ID}/media",
            {"media_type": "REELS", "video_url": url, "caption": caption},
        )
    else:
        container = _post(
            f"{config.IG_USER_ID}/media",
            {"image_url": url, "caption": caption},
        )

    creation_id = container["id"]
    _wait_until_ready(creation_id)
    return _publish_container(creation_id)
