"""Facebook Page'e metin, görsel veya video paylaşımı."""

from __future__ import annotations

import json

import requests

from . import config


class FacebookError(RuntimeError):
    pass


_SAYFA_TOKEN: str | None = None


def _sayfa_token() -> str:
    """Sayfa uclarina gonderi atmak Page access token'i ister.

    META_ACCESS_TOKEN bir kullanici ya da sistem kullanicisi token'i ise,
    tum izinler verilmis olsa bile Sayfa ucu "(#200) publish_actions ...
    deprecated" hatasi donuyor. Dogrusu, eldeki token ile sayfanin kendi
    token'ini cekip onu kullanmak. Cekilemezse eski davranisa donulur ki
    hata mesaji Facebook'tan gelsin, buradan degil.
    """
    global _SAYFA_TOKEN
    if _SAYFA_TOKEN:
        return _SAYFA_TOKEN

    try:
        cevap = requests.get(
            f"{config.GRAPH_BASE}/{config.FB_PAGE_ID}",
            params={"fields": "access_token", "access_token": config.META_TOKEN},
            timeout=60,
        )
        veri = cevap.json()
        bulunan = veri.get("access_token")
        if bulunan:
            _SAYFA_TOKEN = bulunan
            print("  (Facebook Page token'i alindi)")
            return _SAYFA_TOKEN
        neden = (veri.get("error") or {}).get("message", "sayfa token alani bos")
        print(f"  (Page token alinamadi: {neden})")
    except Exception as exc:  # noqa: BLE001
        print(f"  (Page token alinamadi: {exc})")

    _SAYFA_TOKEN = config.META_TOKEN
    return _SAYFA_TOKEN


def _post(base: str, path: str, params: dict) -> dict:
    params = {**params, "access_token": _sayfa_token()}
    response = requests.post(f"{base}/{path}", data=params, timeout=180)
    payload = response.json()
    if "error" in payload:
        raise FacebookError(payload["error"].get("message", str(payload["error"])))
    return payload


def _publish_carousel(caption: str, media_paths: list[str]) -> str:
    """Birden çok görseli tek bir sayfa gönderisinde paylaşır.

    Görseller önce published=false ile yüklenir, sonra hepsi
    attached_media olarak tek bir feed gönderisine bağlanır.
    """
    urls = [config.media_url(p) for p in media_paths]

    if config.DRY_RUN:
        for url in urls:
            print(f"  [DRY RUN] Facebook carousel ← {url}")
        return "dry-run"

    photo_ids = []
    for url in urls:
        uploaded = _post(
            config.GRAPH_BASE,
            f"{config.FB_PAGE_ID}/photos",
            {"url": url, "published": "false"},
        )
        photo_ids.append(uploaded["id"])

    params = {"message": caption}
    for i, photo_id in enumerate(photo_ids):
        params[f"attached_media[{i}]"] = json.dumps({"media_fbid": photo_id})

    result = _post(config.GRAPH_BASE, f"{config.FB_PAGE_ID}/feed", params)
    return result.get("id", "")


def publish(caption: str, media_path: str | list[str] | None, is_video: bool = False) -> str:
    if not config.FB_PAGE_ID:
        raise FacebookError("FB_PAGE_ID tanımlı değil.")

    if isinstance(media_path, list):
        if len(media_path) == 1:
            media_path = media_path[0]
        else:
            return _publish_carousel(caption, media_path)

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
