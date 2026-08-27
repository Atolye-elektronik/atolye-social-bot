"""Pinterest arayüzünden pin oluşturma.

Akış, elle pin atarkenki adımların aynısı:

    pin oluşturma ekranı → görseli yükle → başlık, açıklama, bağlantı →
    pano seç → Kaydet

Görsel repo içinde bir dosya olabilir ya da Shopify CDN adresi olabilir;
tarayıcıya dosya vermek gerektiği için adres verilmişse önce geçici bir
dosyaya indirilir.
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import urllib.parse

import requests

from .. import config, pinterest
from . import selectors
from .session import (
    LOG_DIR,
    OturumDustu,
    StudioError,
    bekle,
    dokum,
    gorunmesini_bekle,
    ilk_gorunen,
    ilk_var_olan,
    kaybolmasini_bekle,
)
from .session import pinterest as pinterest_oturumu

# Pin başlığı 100, açıklama 500 karakter — arayüz API'den daha sıkı davranıyor.
BASLIK_MAX = pinterest.TITLE_MAX
ACIKLAMA_MAX = 500

PIN_ADRES_RE = re.compile(r"/pin/(\d+)")

# Pano adı: post dosyasındaki `pinterest_board`, yoksa bu değişken.
# Arayüz yolunda pano ADI gerekiyor (ID ile arama kutusu çalışmıyor).
VARSAYILAN_PANO = (
    os.environ.get("PINTEREST_BOARD", "").strip()
    or (config.PINTEREST_BOARD_ID if not config.PINTEREST_BOARD_ID.isdigit() else "")
)


def _sessizlestir(dosya: pathlib.Path, gecici: list[pathlib.Path]) -> pathlib.Path:
    """Videonun ses izini söker; Pinterest'e sessiz kopya gider.

    27.08.2026: Pinterest videolarımıza SES TELİFİ ihlali verdi. Videolara
    gömdüğümüz parçalar YouTube Ses Kitaplığı'ndan geliyor; o lisans YouTube
    için net ama Pinterest kendi tarayıcısıyla çalışıyor ve eşleşme buluyor.

    Pinterest akışında videolar zaten sessiz oynadığı için ses orada hiçbir
    şey kazandırmıyor — sadece risk getiriyordu. TikTok/Reels/Shorts'ta ses
    şart olduğu için kaynak mp4'e dokunulmuyor, yalnız Pinterest kopyası
    sessizleştiriliyor.

    Ses izi kopyalama ile atılıyor (yeniden kodlama yok), görüntü birebir aynı.
    """
    if shutil.which("ffmpeg") is None:
        # Gurultulu basarisizlik: sesli yuklemektense pin atmamak yeglenir.
        raise StudioError(
            "ffmpeg bulunamadı — Pinterest'e sesli video yüklenemez (ses telifi). "
            "İş akışına ffmpeg kurulumu ekle ya da postu elle at."
        )
    hedef = pathlib.Path(tempfile.mkdtemp(prefix="pinterest-sessiz-")) / dosya.name
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(dosya),
         "-c", "copy", "-an", str(hedef)],
        check=True,
    )
    gecici.append(hedef)
    print(f"  🔇 Pinterest kopyası sessizleştirildi: {hedef.name}")
    return hedef


def _yerel_dosya(yol: str, gecici: list[pathlib.Path]) -> pathlib.Path:
    """Tarayıcıya verilecek yerel dosyayı hazırlar; adres verilmişse indirir."""
    if not yol.startswith(("http://", "https://")):
        dosya = pathlib.Path(yol)
        if not dosya.exists():
            raise StudioError(f"Görsel bulunamadı: {yol}")
        return dosya

    ad = pathlib.Path(urllib.parse.urlparse(yol).path).name or "gorsel.jpg"
    if "." not in ad:
        ad += ".jpg"

    hedef = pathlib.Path(tempfile.mkdtemp(prefix="pinterest-")) / ad
    with requests.get(yol, stream=True, timeout=120) as r:
        r.raise_for_status()
        with hedef.open("wb") as f:
            for parca in r.iter_content(chunk_size=65536):
                f.write(parca)

    gecici.append(hedef)
    return hedef


def _metin_yaz(page, secenekler: list[str], metin: str, ad: str) -> None:
    """Alanı bulur ve yazar.

    Açıklama alanı contenteditable (zengin metin) olduğu için `fill` her
    zaman çalışmıyor; tıklayıp klavyeden yazmaya düşüyoruz.
    """
    if not metin:
        return
    alan = gorunmesini_bekle(page, secenekler, ad)
    try:
        alan.fill(metin)
    except Exception:  # noqa: BLE001 - contenteditable; klavyeyle yazacağız
        alan.click()
        bekle(0.5)
        page.keyboard.type(metin, delay=8)
    bekle(0.5)


def _pano_sec(page, pano: str) -> None:
    """Pano açılır listesini açar ve istenen panoyu seçer.

    Pano satırlarının test-id'si panonun adını taşıyor
    (`board-row-Arduino ve Robotik Projeler`), yani adı bilince satırı
    doğrudan seçebiliyoruz. Bulamazsak arama kutusuna yazıp tekrar bakarız.
    """
    if not pano:
        # Pano verilmediyse Pinterest'in seçili bıraktığı panoya gider.
        return

    dugme = gorunmesini_bekle(page, selectors.PANO_DUGMESI, "pano seçici")
    dugme.click()
    bekle(1.5)

    hedef = selectors.PANO_SATIRI_KALIBI.format(ad=pano)
    satir = ilk_gorunen(page, [hedef], timeout=4000)

    if satir is None:
        arama = ilk_gorunen(page, selectors.PANO_ARAMA, timeout=5000)
        if arama is not None:
            arama.fill(pano)
            bekle(2)
        satir = ilk_gorunen(page, [hedef], timeout=4000)

    if satir is None:
        mevcut = []
        for el in page.locator(selectors.PANO_SATIRI[0]).all():
            with contextlib.suppress(Exception):
                mevcut.append((el.get_attribute("data-test-id") or "")[len("board-row-"):])
        dokum(page, "pano-bulunamadi")
        raise StudioError(
            f"'{pano}' panosu listede bulunamadı. "
            f"Mevcut panolar: {', '.join(a for a in mevcut if a) or '(liste okunamadı)'}"
        )

    satir.click()
    bekle(1.5)


def _pin_id(page) -> str:
    """Yayınlanan pin'in ID'sini adres çubuğundan ya da onay bağlantısından okur."""
    eslesme = PIN_ADRES_RE.search(page.url)
    if eslesme:
        return eslesme.group(1)

    bag = ilk_gorunen(page, ["a[href*='/pin/']"], timeout=5000)
    if bag is not None:
        with contextlib.suppress(Exception):
            eslesme = PIN_ADRES_RE.search(bag.get_attribute("href") or "")
            if eslesme:
                return eslesme.group(1)
    return "yayinlandi"


def studio_paylas(
    caption: str,
    media_path: str | list[str] | None,
    is_video: bool = False,
    extra: dict | None = None,
) -> str:
    extra = extra or {}

    if not media_path:
        raise StudioError("Pinterest için post dosyasına 'media:' satırı ekle.")

    yollar = media_path if isinstance(media_path, list) else [media_path]
    if len(yollar) > 1:
        # Arayüzde organik karusel pin yok; kapak görselini atıyoruz.
        print(f"  (Pinterest arayüzü tek görsel alıyor — {len(yollar)} slide'ın ilki kullanıldı)")
    kaynak = yollar[0]

    baslik = pinterest.title_from(caption, extra)[:BASLIK_MAX]
    aciklama = pinterest.description_from(caption)[:ACIKLAMA_MAX]
    link = pinterest.link_from(caption, extra)
    pano = (extra.get("pinterest_board") or VARSAYILAN_PANO or "").strip()

    if config.DRY_RUN:
        print(f"  [DRY RUN] Pinterest (arayüz) ← {kaynak}")
        print(f"  [DRY RUN] pano: {pano or '(varsayılan)'} | başlık: {baslik!r} | bağlantı: {link}")
        return "dry-run"

    gecici: list[pathlib.Path] = []
    try:
        dosya = _yerel_dosya(kaynak, gecici)
        if is_video or dosya.suffix.lower() in (".mp4", ".mov", ".m4v"):
            dosya = _sessizlestir(dosya, gecici)

        with pinterest_oturumu(selectors.PIN_OLUSTUR) as page:
            # Yeni adres açılmazsa eski pin-builder'a düş.
            if ilk_gorunen(page, selectors.OLUSTURMA_ISARETLERI, timeout=8000) is None:
                page.goto(selectors.PIN_OLUSTUR_ESKI, wait_until="domcontentloaded")
                gorunmesini_bekle(page, selectors.OLUSTURMA_ISARETLERI, "pin oluşturma ekranı")

            girdi = ilk_var_olan(page, selectors.DOSYA_GIRISI)
            if girdi is None:
                dokum(page, "dosya-girisi-yok")
                raise StudioError(
                    "Pin oluşturma ekranında dosya alanı bulunamadı. "
                    "src/pinterest_studio/selectors.py içindeki DOSYA_GIRISI'ni güncelle."
                )
            girdi.set_input_files(str(dosya))
            print(f"  görsel yükleniyor: {dosya.name}")

            kaybolmasini_bekle(page, selectors.YUKLENIYOR)
            gorunmesini_bekle(page, selectors.ONIZLEME, "yüklenen görselin önizlemesi", timeout=180000)

            _metin_yaz(page, selectors.BASLIK_ALANI, baslik, "başlık alanı")
            _metin_yaz(page, selectors.ACIKLAMA_ALANI, aciklama, "açıklama alanı")
            if link:
                _metin_yaz(page, selectors.LINK_ALANI, link, "bağlantı alanı")

            _pano_sec(page, pano)

            kaydet = gorunmesini_bekle(page, selectors.KAYDET_DUGMESI, "Kaydet düğmesi")
            kaydet.click()
            print("  kaydediliyor...")

            bekle(4)
            if ilk_gorunen(page, selectors.BASARI_ISARETLERI, timeout=45000) is None:
                hata = ilk_gorunen(page, selectors.HATA_ISARETLERI, timeout=2000)
                dokum(page, "yayinlanamadi")
                mesaj = ""
                with contextlib.suppress(Exception):
                    mesaj = hata.inner_text().strip() if hata is not None else ""
                raise StudioError(
                    "Pin'in yayınlandığına dair onay görünmedi. "
                    + (f"Sayfadaki uyarı: {mesaj}" if mesaj else f"Ekran görüntüsü: {LOG_DIR}/")
                )

            return _pin_id(page)
    finally:
        for yol in gecici:
            with contextlib.suppress(OSError):
                yol.unlink()


def publish(
    caption: str,
    media_path: str | list[str] | None,
    is_video: bool = False,
    extra: dict | None = None,
) -> str:
    """main.py'nin çağırdığı giriş noktası.

    Oturum düşmüşse hatayı olduğu gibi bırakıyoruz: TikTok'taki gibi resmî
    API'ye düşmek burada işe yaramaz, çünkü API yolu onaylı bir developer app
    istiyor ve onaysızken pin'i kimseye göstermiyor. Sessizce görünmez bir pin
    atmaktansa hata verip haber vermek daha dürüst.
    """
    return studio_paylas(caption, media_path, is_video, extra)


__all__ = ["publish", "studio_paylas", "OturumDustu", "StudioError"]
