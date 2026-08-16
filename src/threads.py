"""Threads (Meta) API ile paylaşım.

Threads, Instagram/Facebook ile aynı şirketin olmasına rağmen ayrı bir API
kullanıyor: adres graph.facebook.com değil **graph.threads.net**, token da
META_ACCESS_TOKEN değil kendi token'ı (THREADS_ACCESS_TOKEN).

Akış Instagram'daki ile aynı mantıkta: önce bir "kapsayıcı" (container)
oluşturuluyor, hazır olunca yayınlanıyor.

Gerekli ortam değişkenleri / secret'lar:
  THREADS_ACCESS_TOKEN   tools/threads_auth.py ile üretilir (60 gün geçerli)
  THREADS_USER_ID        opsiyonel — boşsa token'dan otomatik bulunur

Post dosyasında kullanılabilecek isteğe bağlı alanlar:
  threads_text:          Threads'e özel metin (yoksa post metni kullanılır)
  threads_reply_control: everyone | accounts_you_follow | mentioned_only

Sınırlar (Threads tarafı):
  - metin en fazla 500 karakter
  - carousel 2-20 görsel
  - günde en fazla 250 paylaşım
"""

from __future__ import annotations

import time

import requests

from . import config

# Threads metin sınırı.
MAX_TEXT = 500

# Carousel sınırları.
MIN_CAROUSEL = 2
MAX_CAROUSEL = 20

REPLY_CONTROLS = ("everyone", "accounts_you_follow", "mentioned_only")


class ThreadsError(RuntimeError):
    pass


def _post(path: str, params: dict) -> dict:
    params = {**params, "access_token": config.THREADS_TOKEN}
    response = requests.post(f"{config.THREADS_BASE}/{path}", data=params, timeout=180)
    payload = response.json()
    if "error" in payload:
        raise ThreadsError(payload["error"].get("message", str(payload["error"])))
    return payload


def _get(path: str, params: dict) -> dict:
    params = {**params, "access_token": config.THREADS_TOKEN}
    response = requests.get(f"{config.THREADS_BASE}/{path}", params=params, timeout=60)
    payload = response.json()
    if "error" in payload:
        raise ThreadsError(payload["error"].get("message", str(payload["error"])))
    return payload


def user_id() -> str:
    """Threads kullanıcı ID'si — verilmemişse token'ın sahibinden okunur."""
    if config.THREADS_USER_ID:
        return config.THREADS_USER_ID
    me = _get("me", {"fields": "id,username"})
    found = str(me.get("id", ""))
    if not found:
        raise ThreadsError("Threads kullanici ID'si bulunamadi.")
    # Aynı çalışmada tekrar sorulmasın.
    config.THREADS_USER_ID = found
    print(f"  (Threads kullanici: @{me.get('username', '?')} / {found})")
    return found


def _link_ya_da_etiket(blok: str) -> bool:
    """Blok sipariş bağlantısı ya da etiket satırı mı?"""
    return "http://" in blok or "https://" in blok or blok.lstrip().startswith("#")


def _kisalt(text: str, limit: int = MAX_TEXT) -> str:
    """Metni Threads sınırına sığdırır, kelimenin ortasından kesmez.

    Sondaki sipariş bağlantısı ve etiket blokları korunur; yer açmak
    gerekirse gövde kısaltılır. Düz kesmede 500 karakter sınırı tam da
    satın alma çağrısını götürüyordu.
    """
    text = text.strip()
    if len(text) <= limit:
        return text

    bloklar = text.split("\n\n")
    kuyruk: list[str] = []
    while len(bloklar) > 1 and _link_ya_da_etiket(bloklar[-1]):
        kuyruk.insert(0, bloklar.pop())

    sonek = "\n\n".join(kuyruk)
    govde = "\n\n".join(bloklar).strip()

    # Korunacak kuyruk tek başına sınırı dolduruyorsa kurtaracak bir şey yok.
    pay = limit - len(sonek) - 2 if sonek else limit
    if pay < 40:
        sonek = ""
        govde = text
        pay = limit

    kesik = govde[: pay - 1]
    bosluk = kesik.rfind(" ")
    if bosluk > pay * 0.6:
        kesik = kesik[:bosluk]
    kesik = kesik.rstrip(" ,;:-") + "…"

    sonuc = f"{kesik}\n\n{sonek}" if sonek else kesik
    print(f"  (metin {len(text)} karakterdi, Threads icin {len(sonuc)} karaktere kisaltildi)")
    return sonuc


def _wait_until_ready(container_id: str, timeout_seconds: int = 300) -> None:
    """Kapsayıcı işlenene kadar bekler.

    Threads dokümanı video kapsayıcıları için yayınlamadan önce ~30 saniye
    beklemeyi öneriyor; durumu sorgulamak daha kesin sonuç veriyor.
    """
    deadline = time.time() + timeout_seconds
    last: dict = {}
    while time.time() < deadline:
        try:
            last = _get(container_id, {"fields": "status,error_message"})
        except ThreadsError:
            time.sleep(5)
            continue

        status = last.get("status")
        if status in ("FINISHED", "PUBLISHED"):
            return
        if status == "ERROR":
            raise ThreadsError(f"Medya islenemedi: {last.get('error_message')}")
        if status == "EXPIRED":
            raise ThreadsError("Kapsayici zaman asimina ugradi (24 saat gecti).")
        time.sleep(5)

    raise ThreadsError(f"Medya isleme zaman asimina ugradi: {last}")


def _publish_container(uid: str, creation_id: str) -> str:
    last_error: Exception | None = None
    for _ in range(6):
        try:
            published = _post(f"{uid}/threads_publish", {"creation_id": creation_id})
            return str(published["id"])
        except ThreadsError as exc:
            message = str(exc).lower()
            if "not ready" not in message and "not available" not in message:
                raise
            last_error = exc
            print("  (medya henuz hazir degil, tekrar denenecek)")
            time.sleep(10)
    raise ThreadsError(f"Yayinlanamadi: {last_error}")


def _publish_carousel(uid: str, text: str, media_paths: list[str], reply_control: str) -> str:
    """2-20 görselden oluşan Threads carousel'i."""
    if len(media_paths) > MAX_CAROUSEL:
        print(f"  (Threads en fazla {MAX_CAROUSEL} gorsel kabul ediyor, fazlasi atlandi)")
        media_paths = media_paths[:MAX_CAROUSEL]

    urls = [config.media_url(p) for p in media_paths]

    if config.DRY_RUN:
        for url in urls:
            print(f"  [DRY RUN] Threads carousel ← {url}")
        return "dry-run"

    children: list[str] = []
    for url in urls:
        child = _post(
            f"{uid}/threads",
            {
                "media_type": _media_type(url),
                _url_field(url): url,
                "is_carousel_item": "true",
            },
        )
        children.append(str(child["id"]))

    for child_id in children:
        _wait_until_ready(child_id)

    params = {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "text": text,
    }
    if reply_control:
        params["reply_control"] = reply_control

    container = _post(f"{uid}/threads", params)
    creation_id = str(container["id"])
    _wait_until_ready(creation_id)
    return _publish_container(uid, creation_id)


def _media_type(url: str) -> str:
    return "VIDEO" if url.lower().split("?")[0].endswith((".mp4", ".mov", ".m4v")) else "IMAGE"


def _url_field(url: str) -> str:
    return "video_url" if _media_type(url) == "VIDEO" else "image_url"


def publish(
    caption: str,
    media_path: str | list[str] | None,
    is_video: bool = False,
    extra: dict | None = None,
) -> str:
    if not config.THREADS_TOKEN:
        raise ThreadsError("THREADS_ACCESS_TOKEN tanimli degil.")

    extra = extra or {}
    text = _kisalt(str(extra.get("threads_text") or caption))

    reply_control = str(extra.get("threads_reply_control") or "").strip().lower()
    if reply_control and reply_control not in REPLY_CONTROLS:
        print(f"  (bilinmeyen threads_reply_control: {reply_control}, yok sayildi)")
        reply_control = ""

    if isinstance(media_path, list):
        if len(media_path) == 1:
            media_path = media_path[0]
        elif len(media_path) >= MIN_CAROUSEL:
            uid = "dry-run" if config.DRY_RUN else user_id()
            return _publish_carousel(uid, text, media_path, reply_control)
        else:
            media_path = None

    if config.DRY_RUN:
        target = config.media_url(media_path) if media_path else "(sadece metin)"
        print(f"  [DRY RUN] Threads → {target}")
        print(f"  [DRY RUN] metin: {len(text)} karakter")
        return "dry-run"

    uid = user_id()

    params: dict = {"text": text}
    if reply_control:
        params["reply_control"] = reply_control

    if media_path:
        url = config.media_url(media_path)
        tip = "VIDEO" if (is_video or _media_type(url) == "VIDEO") else "IMAGE"
        params["media_type"] = tip
        params["video_url" if tip == "VIDEO" else "image_url"] = url
    else:
        # Threads, Instagram'ın aksine sadece metin paylaşımı kabul ediyor.
        params["media_type"] = "TEXT"

    container = _post(f"{uid}/threads", params)
    creation_id = str(container["id"])
    # Sadece metin gönderilerinde işlenecek medya yok, beklemeye gerek kalmıyor.
    if params["media_type"] != "TEXT":
        _wait_until_ready(creation_id)
    return _publish_container(uid, creation_id)
