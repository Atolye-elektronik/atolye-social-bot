"""Pinterest için kalıcı tarayıcı oturumu (Playwright).

Pinterest'in resmî API'si (src/pinterest.py) bir işletme hesabı ve onaylı
developer app istiyor; onaylanana kadar da attığın pin'ler herkese açık
görünmüyor. Bu modül o kapıyı hiç çalmaz: gerçek bir Chromium açar ve senin
oturum çerezlerinle pin'i normal arayüzden atar. Kişisel hesapla çalışır.

Oturum nereden gelir?

  Yerelde  — `python tools/pinterest_studio_login.py` bir kez çalıştırılır,
             tarayıcı açılır, elle giriş yaparsın; çerezler
             .pinterest_studio_state.json dosyasına yazılır (git'e girmez).

  CI'da    — aynı dosyanın base64'ü PINTEREST_STUDIO_COOKIES secret'ına konur.

TikTok Studio modülüyle aynı bilinçli tercihler geçerli: oturum düşünce iş
çökmez, `OturumDustu` fırlatır; her hatada ekran görüntüsü + HTML dökümü
logs/pinterest-studio altına yazılır.
"""

from __future__ import annotations

import base64
import contextlib
import datetime as dt
import json
import os
import pathlib
import time
from typing import Iterator

STATE_PATH = pathlib.Path(
    os.environ.get("PINTEREST_STUDIO_STATE", ".pinterest_studio_state.json")
)
LOG_DIR = pathlib.Path(os.environ.get("PINTEREST_STUDIO_LOG_DIR", "logs/pinterest-studio"))

# Görünür tarayıcı: yerelde giriş yaparken ve hata ayıklarken işe yarıyor.
HEADFUL = os.environ.get("PINTEREST_STUDIO_HEADFUL", "false").lower() in ("1", "true", "yes")

# Adımlar arası bekleme çarpanı. CI makineleri yavaş olabiliyor.
YAVASLIK = float(os.environ.get("PINTEREST_STUDIO_YAVASLIK", "1"))

# Hangi tarayıcı kullanılsın. Boş bırakılırsa önce Playwright'ın kendi
# Chromium'u denenir, açılmazsa sistemdeki Chrome ve Edge'e düşülür.
KANAL = os.environ.get("PINTEREST_STUDIO_KANAL", "").strip()
KANAL_SIRASI = (None, "chrome", "msedge")

TARAYICI_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

TARAYICI_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]


class StudioError(RuntimeError):
    """Pinterest arayüz otomasyonunda genel hata."""


class OturumDustu(StudioError):
    """Çerezler geçersiz — elle yeniden giriş gerekiyor."""

    def __init__(self, detay: str = "") -> None:
        super().__init__(
            "Pinterest oturumu düşmüş. "
            "Kendi bilgisayarında `python tools/pinterest_studio_login.py` çalıştırıp "
            "çıkan base64 değeri PINTEREST_STUDIO_COOKIES secret'ına yeniden yaz. "
            + detay
        )


def _playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - kurulum hatası
        raise StudioError(
            "Playwright kurulu değil. Kurmak için:\n"
            "    pip install playwright\n"
            "    python -m playwright install chromium"
        ) from exc
    return sync_playwright


# --- Oturum dosyası ----------------------------------------------------------


def storage_state() -> dict | None:
    """Çerezleri secret'tan ya da yerel dosyadan okur."""
    ham = os.environ.get("PINTEREST_STUDIO_COOKIES", "").strip()
    if ham:
        try:
            if ham.lstrip().startswith("{"):
                return json.loads(ham)
            return json.loads(base64.b64decode(ham).decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            raise OturumDustu(f"(PINTEREST_STUDIO_COOKIES okunamadı: {exc})") from exc

    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise OturumDustu(f"({STATE_PATH} bozuk: {exc})") from exc

    return None


def storage_state_yaz(state: dict) -> None:
    """Tazelenmiş çerezleri yerel dosyaya geri yazar."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def girisli_mi(cerezler) -> bool:
    """Çerez listesine bakıp giriş yapılmış mı söyler.

    `cerezler` hem tarayıcı context'inin döndürdüğü liste hem de storage
    state'in içindeki liste olabilir — ikisi de aynı biçimde geliyor.
    """
    from . import selectors

    for c in cerezler or []:
        if c.get("name") == selectors.GIRIS_CEREZI:
            return str(c.get("value", "")).strip('"') == selectors.GIRIS_CEREZ_DEGERI
    return False


def cerez_son_kullanma(state: dict | None = None) -> dt.datetime | None:
    """Oturumu ayakta tutan çerezin ne zaman düşeceğini söyler."""
    from . import selectors

    state = state or storage_state()
    if not state:
        return None
    zamanlar = [
        c.get("expires", -1)
        for c in state.get("cookies", [])
        if c.get("name") in selectors.OTURUM_CEREZLERI
    ]
    zamanlar = [z for z in zamanlar if isinstance(z, (int, float)) and z > 0]
    if not zamanlar:
        return None
    return dt.datetime.fromtimestamp(min(zamanlar), dt.timezone.utc)


# --- Tarayıcı ----------------------------------------------------------------


def tarayici_ac(p, headless: bool = True):
    """Tarayıcıyı açar; paket Chromium başlamazsa kurulu Chrome/Edge'e düşer."""
    adaylar = [KANAL] if KANAL else list(KANAL_SIRASI)
    son_hata = None

    for kanal in adaylar:
        try:
            return p.chromium.launch(headless=headless, channel=kanal, args=TARAYICI_ARGS)
        except Exception as exc:  # noqa: BLE001 - sıradaki kanalı deneyeceğiz
            son_hata = exc
            print(f"  ⚠️  {kanal or 'paket Chromium'} açılamadı, sıradaki deneniyor...")

    raise StudioError(
        "Hiçbir tarayıcı açılamadı (paket Chromium, Chrome, Edge). "
        f"Son hata: {son_hata}"
    )


@contextlib.contextmanager
def pinterest(hedef: str | None = None, kaydet: bool = True) -> Iterator:
    """Girişli bir Pinterest sayfası açar.

        with pinterest(selectors.PIN_OLUSTUR) as page:
            ...

    Oturum geçersizse `OturumDustu` fırlatır.
    """
    from . import selectors

    state = storage_state()
    if state is None:
        raise OturumDustu("(Ne PINTEREST_STUDIO_COOKIES secret'ı ne de yerel dosya var.)")
    if not girisli_mi(state.get("cookies")):
        # Tarayıcı açıp anlamaya çalışmaya gerek yok: kayıtta giriş yok.
        raise OturumDustu("(Kayıtlı oturumda giriş yok — `_auth` çerezi 1 değil.)")

    sync_playwright = _playwright()
    with sync_playwright() as p:
        browser = tarayici_ac(p, headless=not HEADFUL)
        context = browser.new_context(
            storage_state=state,
            user_agent=TARAYICI_UA,
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
            viewport={"width": 1440, "height": 900},
        )
        context.set_default_timeout(int(30000 * YAVASLIK))
        page = context.new_page()

        try:
            page.goto(hedef or selectors.ANASAYFA, wait_until="domcontentloaded")
            _giris_dogrula(page)
            yield page
        finally:
            if kaydet:
                with contextlib.suppress(Exception):
                    storage_state_yaz(context.storage_state())
            with contextlib.suppress(Exception):
                context.close()
                browser.close()


def _giris_dogrula(page) -> None:
    from . import selectors

    bekle(2)
    adres = page.url.lower()
    if any(parca in adres for parca in selectors.GIRIS_ADRES_PARCALARI):
        dokum(page, "oturum-dustu")
        raise OturumDustu(f"(Giriş sayfasına yönlendirildi: {page.url})")

    if ilk_gorunen(page, selectors.GIRIS_ISARETLERI, timeout=3000):
        dokum(page, "oturum-dustu")
        raise OturumDustu("(Sayfada giriş formu göründü.)")


# --- Yardımcılar -------------------------------------------------------------


def bekle(saniye: float) -> None:
    time.sleep(saniye * YAVASLIK)


def ilk_gorunen(kok, secenekler: list[str], timeout: int = 10000):
    """Listedeki seçicileri sırayla dener, ilk görünen locator'ı döndürür.

    Hiçbiri görünmezse None döner — hata fırlatmaz, çünkü çağıranlar çoğu
    yerde "varsa kullan" davranışı istiyor.
    """
    bitis = time.time() + (timeout / 1000) * YAVASLIK
    while True:
        for secici in secenekler:
            try:
                aday = kok.locator(secici).first
                if aday.is_visible(timeout=250):
                    return aday
            except Exception:  # noqa: BLE001 - seçici geçersiz ya da öğe yok
                continue
        if time.time() >= bitis:
            return None
        time.sleep(0.4)


def ilk_var_olan(kok, secenekler: list[str], timeout: int = 15000):
    """`ilk_gorunen` gibi ama görünürlük aramaz, DOM'da var olması yeter.

    Dosya seçiciler gizli tutuluyor (`input[type=file]` görünmez bir öğe),
    ama Playwright gizli input'a da dosya verebiliyor.
    """
    bitis = time.time() + (timeout / 1000) * YAVASLIK
    while True:
        for secici in secenekler:
            try:
                aday = kok.locator(secici).first
                if aday.count() > 0:
                    return aday
            except Exception:  # noqa: BLE001 - seçici geçersiz ya da öğe yok
                continue
        if time.time() >= bitis:
            return None
        time.sleep(0.4)


def gorunmesini_bekle(page, secenekler: list[str], ad: str, timeout: int = 30000):
    """`ilk_gorunen` gibi, ama bulamazsa döküm alıp hata fırlatır."""
    aday = ilk_gorunen(page, secenekler, timeout=timeout)
    if aday is None:
        dokum(page, f"bulunamadi-{ad}")
        raise StudioError(
            f"Pinterest arayüzünde '{ad}' bulunamadı. Arayüz değişmiş olabilir — "
            f"src/pinterest_studio/selectors.py içindeki seçicileri güncelle. "
            f"Ekran görüntüsü: {LOG_DIR}/"
        )
    return aday


def kaybolmasini_bekle(page, secenekler: list[str], timeout: int = 300000) -> None:
    """Öğeler ekrandan silinene kadar bekler (görsel yüklenirken kullanılıyor)."""
    bitis = time.time() + (timeout / 1000) * YAVASLIK
    while time.time() < bitis:
        if ilk_gorunen(page, secenekler, timeout=1000) is None:
            return
        time.sleep(2)


def dokum(page, ad: str) -> pathlib.Path | None:
    """Hata anında ekran görüntüsü + HTML yazar; CI bunları artifact yapar."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    damga = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    kok = LOG_DIR / f"{damga}-{ad}"
    try:
        page.screenshot(path=str(kok.with_suffix(".png")), full_page=True)
        kok.with_suffix(".html").write_text(page.content(), encoding="utf-8")
        print(f"  📸 döküm: {kok}.png")
        return kok.with_suffix(".png")
    except Exception:  # noqa: BLE001 - döküm alınamaması işi bozmasın
        return None


# --- Sağlık kontrolü ---------------------------------------------------------


def saglik_kontrol() -> int:
    """Oturum ayakta mı, çerez ne zaman düşecek — CI'da günlük çalışır."""
    from . import selectors

    son = cerez_son_kullanma()
    if son:
        kalan = son - dt.datetime.now(dt.timezone.utc)
        print(f"Çerez son kullanma: {son:%Y-%m-%d %H:%M} UTC ({kalan.days} gün kaldı)")
        if kalan.days < 7:
            print(
                "⚠️  Oturum bir hafta içinde düşecek. "
                "`python tools/pinterest_studio_login.py` ile yenile."
            )

    try:
        with pinterest(selectors.ANASAYFA):
            print("✅ Pinterest oturumu geçerli.")
        return 0
    except OturumDustu as exc:
        print(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(saglik_kontrol())
