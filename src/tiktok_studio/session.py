"""TikTok Studio için kalıcı tarayıcı oturumu (Playwright).

TikTok Studio'nun resmi bir API'si yok. Bu modül gerçek bir Chromium açar ve
senin oturum çerezlerinle çalışır. Oturum bilgisi Playwright'ın "storage
state" JSON'unda tutulur.

Oturum nereden gelir?

  Yerelde  — `python tools/tiktok_studio_login.py` bir kez çalıştırılır,
             tarayıcı açılır, elle giriş yaparsın; çerezler
             .tiktok_studio_state.json dosyasına yazılır (git'e girmez).

  CI'da    — aynı dosyanın base64'ü TIKTOK_STUDIO_COOKIES secret'ına konur.

Bilinçli tercihler — CI'da tarayıcı otomasyonu kırılgan olduğu için:

  * Oturum düştüğünde iş çökmez, `OturumDustu` hatası fırlatır. Çağıran taraf
    (src/tiktok.py) bunu yakalayıp resmî API'nin taslak moduna düşer.
  * Her hatada ekran görüntüsü + HTML dökümü logs/tiktok-studio altına yazılır;
    CI bunları artifact olarak yükler, körlemesine hata aramazsın.
  * Çerezler her çalışmada tazelenir; yerelde dosyaya geri yazılır. CI'da
    secret güncellenemediği için `saglik_kontrol()` çerezin ne zaman
    düşeceğini önceden söyler.
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
    os.environ.get("TIKTOK_STUDIO_STATE", ".tiktok_studio_state.json")
)
LOG_DIR = pathlib.Path(os.environ.get("TIKTOK_STUDIO_LOG_DIR", "logs/tiktok-studio"))

# Görünür tarayıcı: yerelde giriş yaparken ve hata ayıklarken işe yarıyor.
HEADFUL = os.environ.get("TIKTOK_STUDIO_HEADFUL", "false").lower() in ("1", "true", "yes")

# Adımlar arası bekleme çarpanı. CI makineleri yavaş olabiliyor.
YAVASLIK = float(os.environ.get("TIKTOK_STUDIO_YAVASLIK", "1"))

# Hangi tarayıcı kullanılsın. Boş bırakılırsa önce Playwright'ın kendi
# Chromium'u denenir (CI'daki Playwright imajında olan bu), açılmazsa
# sistemdeki Chrome ve Edge'e düşülür — bazı Windows kurulumlarında paket
# Chromium "yan yana yapılandırma" hatasıyla hiç başlamıyor. Belirli bir
# tarayıcıyı zorlamak istersen TIKTOK_STUDIO_KANAL=chrome (ya da msedge).
KANAL = os.environ.get("TIKTOK_STUDIO_KANAL", "").strip()

# Kanal verilmediğinde sırayla denenecekler. None = paket Chromium.
KANAL_SIRASI = (None, "chrome", "msedge")

TARAYICI_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class StudioError(RuntimeError):
    """TikTok Studio otomasyonunda genel hata."""


class OturumDustu(StudioError):
    """Çerezler geçersiz — elle yeniden giriş gerekiyor.

    Çağıran taraf bunu yakalayıp yedek yola (resmî API taslak modu) düşebilir.
    """

    def __init__(self, detay: str = "") -> None:
        super().__init__(
            "TikTok Studio oturumu düşmüş. "
            "Kendi bilgisayarında `python tools/tiktok_studio_login.py` çalıştırıp "
            "çıkan base64 değeri TIKTOK_STUDIO_COOKIES secret'ına yeniden yaz. "
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
    ham = os.environ.get("TIKTOK_STUDIO_COOKIES", "").strip()
    if ham:
        try:
            if ham.lstrip().startswith("{"):
                return json.loads(ham)
            return json.loads(base64.b64decode(ham).decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            raise OturumDustu(f"(TIKTOK_STUDIO_COOKIES okunamadı: {exc})") from exc

    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise OturumDustu(f"({STATE_PATH} bozuk: {exc})") from exc

    return None


def storage_state_yaz(state: dict) -> None:
    """Tazelenmiş çerezleri yerel dosyaya geri yazar.

    CI'da secret'ı buradan güncelleyemiyoruz; orada dosya geçici, sadece aynı
    iş içindeki adımlar faydalanır.
    """
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def cerez_son_kullanma(state: dict | None = None) -> dt.datetime | None:
    """Oturumu ayakta tutan çerezin ne zaman düşeceğini söyler.

    TikTok'ta oturumu `sessionid` taşıyor; en erken düşen o.
    """
    state = state or storage_state()
    if not state:
        return None
    zamanlar = [
        c.get("expires", -1)
        for c in state.get("cookies", [])
        if c.get("name") in ("sessionid", "sessionid_ss", "sid_tt")
    ]
    zamanlar = [z for z in zamanlar if isinstance(z, (int, float)) and z > 0]
    if not zamanlar:
        return None
    return dt.datetime.fromtimestamp(min(zamanlar), dt.timezone.utc)


# --- Tarayıcı ----------------------------------------------------------------


TARAYICI_ARGS = [
    # Otomasyon bayrağını kapatmak, Studio'nun bazı bileşenlerinin
    # headless'ta hiç render edilmemesini önlüyor.
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]


def tarayici_ac(p, headless: bool = True):
    """Tarayıcıyı açar; paket Chromium başlamazsa kurulu Chrome/Edge'e düşer.

    Kanal seçimini kullanıcının hatırlamasına gerek kalmasın diye burada
    yapıyoruz: bazı Windows kurulumlarında paket Chromium hiç açılmıyor,
    ama aynı makinede Chrome sorunsuz çalışıyor.
    """
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
def studio(hedef: str | None = None, kaydet: bool = True) -> Iterator:
    """Girişli bir TikTok Studio sayfası açar.

        with studio(selectors.YUKLEME) as page:
            ...

    Oturum geçersizse `OturumDustu` fırlatır.
    """
    from . import selectors

    state = storage_state()
    if state is None:
        raise OturumDustu("(Ne TIKTOK_STUDIO_COOKIES secret'ı ne de yerel dosya var.)")

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
        # TikTok'un tanitim turu (react-joyride) katmani tum tiklamalari
        # yutuyor. Elementi silmek ise yaramadi — React ayni karede geri
        # ekliyor (2026-08-18, 4. kosu). CSS ile hem gizleniyor hem
        # pointer-events kapatiliyor: React elementini korur, savas cikmaz,
        # katman tiklama yutamaz.
        context.add_init_script(
            """
            (() => {
              const stilEkle = () => {
                if (document.getElementById('joyride-kapatici')) return;
                const s = document.createElement('style');
                s.id = 'joyride-kapatici';
                s.textContent = '#react-joyride-portal, .react-joyride__overlay, ' +
                  '.__floater, [data-test-id="overlay"] ' +
                  '{ display: none !important; pointer-events: none !important; }';
                (document.head || document.documentElement).appendChild(s);
              };
              stilEkle();
              new MutationObserver(stilEkle).observe(
                document.documentElement, {childList: true, subtree: true});
            })();
            """
        )
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


def gorunmesini_bekle(kok, secenekler: list[str], ad: str, timeout: int = 30000, sayfa=None):
    """`ilk_gorunen` gibi, ama bulamazsa döküm alıp hata fırlatır.

    `kok` bir iframe olabildiği ve FrameLocator'dan ekran görüntüsü
    alınamadığı için asıl sayfayı ayrıca geçiyoruz.
    """
    aday = ilk_gorunen(kok, secenekler, timeout=timeout)
    if aday is None:
        dokum(sayfa if sayfa is not None else kok, f"bulunamadi-{ad}")
        raise StudioError(
            f"TikTok Studio arayüzünde '{ad}' bulunamadı. "
            f"Arayüz değişmiş olabilir — src/tiktok_studio/selectors.py içindeki "
            f"seçicileri güncelle. Ekran görüntüsü: {LOG_DIR}/"
        )
    return aday


def kaybolmasini_bekle(kok, secenekler: list[str], timeout: int = 600000) -> None:
    """Öğeler ekrandan silinene kadar bekler (video işlenirken kullanılıyor)."""
    bitis = time.time() + (timeout / 1000) * YAVASLIK
    while time.time() < bitis:
        if ilk_gorunen(kok, secenekler, timeout=1000) is None:
            return
        time.sleep(2)


def yukleme_koku(page):
    """Yükleme arayüzü iframe içindeyse frame'i, değilse sayfayı döndürür."""
    from . import selectors

    for secici in selectors.YUKLEME_IFRAME:
        with contextlib.suppress(Exception):
            cerceve = page.frame_locator(secici)
            if cerceve.locator("input[type=file]").count() > 0:
                return cerceve
    return page


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
    """Oturum ayakta mı, çerez ne zaman düşecek — CI'da günlük çalışır.

    Çerezin düşmesine bir haftadan az kaldıysa uyarır; böylece bir paylaşım
    sessizce kaçmadan önce secret'i yenileme fırsatın olur.
    """
    from . import selectors

    son = cerez_son_kullanma()
    if son:
        kalan = son - dt.datetime.now(dt.timezone.utc)
        gun = kalan.days
        print(f"Çerez son kullanma: {son:%Y-%m-%d %H:%M} UTC ({gun} gün kaldı)")
        if gun < 7:
            print(
                "⚠️  Oturum bir hafta içinde düşecek. "
                "`python tools/tiktok_studio_login.py` ile yenile."
            )

    try:
        with studio(selectors.ANASAYFA):
            print("✅ TikTok Studio oturumu geçerli.")
        return 0
    except OturumDustu as exc:
        print(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(saglik_kontrol())
