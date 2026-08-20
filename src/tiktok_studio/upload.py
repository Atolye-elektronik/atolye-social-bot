"""TikTok Studio üzerinden video yükleme ve ileri tarihe zamanlama.

Resmî Content Posting API (src/tiktok.py) denetimden geçmemiş uygulamalarda
videoyu sadece TikTok uygulamasındaki gelen kutusuna bırakabiliyor —
yayınlama kararını elle vermen gerekiyor. Studio ise gerçek arayüz olduğu
için hem doğrudan yayınlayabiliyor hem de TikTok'un kendi zamanlayıcısına
ileri tarih verebiliyor.

İki kullanım yolu var:

  1. Yayıncı olarak — post'un `platforms` alanına `tiktok_studio` yazarsan
     src/main.py zamanı geldiğinde buradan paylaşır.

  2. Zamanlayıcı olarak — `python -m src.tiktok_studio zamanla --gun 7`
     önümüzdeki 7 günün postlarını şimdiden TikTok'a yükleyip TikTok'un
     kendi zamanlayıcısına bırakır. Böylece paylaşım anında CI'ın ayakta
     olmasına gerek kalmaz; oturum düşse bile planlanmış videolar çıkar.

İkinci yol, CI'da tarayıcı otomasyonunun kırılganlığına karşı en iyi
sigorta — bu yüzden önerilen kullanım o.
"""

from __future__ import annotations

import datetime as dt
import os
import pathlib
import re
from zoneinfo import ZoneInfo

from .. import config, posts
from . import selectors
from .session import (
    OturumDustu,
    StudioError,
    bekle,
    dokum,
    gorunmesini_bekle,
    ilk_gorunen,
    kaybolmasini_bekle,
    studio,
    yukleme_koku,
)

TZ = ZoneInfo("Europe/Istanbul")

# TikTok'un zamanlayıcı sınırları: en erken 15 dakika, en geç 10 gün sonrası.
EN_ERKEN = dt.timedelta(minutes=20)
EN_GEC = dt.timedelta(days=10)

# Studio başarısız olursa resmî API'nin taslak moduna düş. Böylece CI'da
# oturum düştüğünde içerik büsbütün kaybolmaz, TikTok uygulamana düşer.
YEDEK_API = os.environ.get("TIKTOK_STUDIO_YEDEK_API", "true").lower() in ("1", "true", "yes")

MAKS_ACIKLAMA = 2200


class ZamanlamaHatasi(StudioError):
    """Zamanlama kurulamadı — video yayınlanmadan durduruldu."""


# --- Açıklama ----------------------------------------------------------------


def _aciklama_yaz(kok, sayfa, metin: str) -> None:
    """Açıklama alanını temizleyip metni yazar.

    Hashtag ve @ yazarken TikTok bir öneri kutusu açıyor; Enter'a basınca
    öneriyi seçip metni bozuyor. Bu yüzden satır sonlarından önce Escape ile
    kutuyu kapatıyoruz.
    """
    alan = gorunmesini_bekle(kok, selectors.ACIKLAMA_ALANI, "açıklama alanı", sayfa=sayfa)
    alan.click()
    bekle(0.5)

    # Editör (Draft.js) yazarken DOM düğümünü yenileyebiliyor; locator
    # üzerinden press/type actionability beklemesine takılıp 45 sn'de
    # düşüyordu (19.08 koşusu). Alan bir kez tıklanıp odaklandıktan sonra
    # tüm girdi sayfa klavyesiyle veriliyor — odaklı öğeye gider, bekleme yok.
    klavye = sayfa.keyboard

    # Studio alana otomatik olarak dosya adını yazıyor — önce onu sil.
    klavye.press("Control+A")
    klavye.press("Delete")
    bekle(0.5)

    satirlar = metin[:MAKS_ACIKLAMA].splitlines() or [""]
    for i, satir in enumerate(satirlar):
        if satir:
            klavye.type(satir, delay=25)
        # Öneri kutusu açıksa kapat, yoksa Escape zararsız.
        klavye.press("Escape")
        if i < len(satirlar) - 1:
            klavye.press("Enter")
    bekle(1)


# --- Zamanlama ---------------------------------------------------------------

def _alan_doldur(kok, alan, deger: str, kaliplar: list[str], secenek: str) -> bool:
    """Tarih/saat alanını doldurur.

    Studio'nun alanları sürüme göre bazen serbest yazılabilir, bazen sadece
    açılır listeden seçilebilir. Önce yazmayı, olmazsa listeden seçmeyi dener.
    """
    try:
        alan.fill(deger, timeout=5000)
        alan.press("Enter")
        bekle(0.5)
        return True
    except Exception:  # noqa: BLE001 - alan salt okunur, listeden seçeceğiz
        pass

    alan.click()
    bekle(1)
    hedef = ilk_gorunen(
        kok, [k.format(deger=secenek) for k in kaliplar], timeout=5000
    )
    if hedef is None:
        return False
    hedef.click()
    bekle(0.5)
    return True


def _zamanla(kok, sayfa, ne_zaman: dt.datetime) -> None:
    """Zamanlama anahtarını açar, tarih ve saati kurar, sonucu DOĞRULAR.

    Doğrulama kritik: zamanlama sessizce kurulamazsa "Yayınla" düğmesi videoyu
    hemen yayınlar. Bu yüzden alanların değerini geri okuyup uymuyorsa
    yayınlamadan hata fırlatıyoruz.
    """
    anahtar = gorunmesini_bekle(
        kok, selectors.ZAMANLA_ANAHTARI, "zamanla anahtarı", sayfa=sayfa
    )
    anahtar.click()
    bekle(2)

    saat_alani = gorunmesini_bekle(kok, selectors.SAAT_ALANI, "saat alanı", sayfa=sayfa)
    saat_metni = ne_zaman.strftime("%H:%M")
    _alan_doldur(kok, saat_alani, saat_metni, selectors.SAAT_SECENEGI, saat_metni)

    tarih_alani = gorunmesini_bekle(
        kok, selectors.TARIH_ALANI, "tarih alanı", sayfa=sayfa
    )
    tarih_metni = ne_zaman.strftime("%Y-%m-%d")
    _alan_doldur(
        kok, tarih_alani, tarih_metni, selectors.TAKVIM_GUNU, str(ne_zaman.day)
    )
    bekle(1)

    _zamanlama_dogrula(kok, sayfa, ne_zaman)


AYLAR_TR = (
    "ocak", "şubat", "mart", "nisan", "mayıs", "haziran",
    "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık",
)


def _tarih_uyuyor(okunan: str, ne_zaman: dt.datetime) -> bool:
    """Alandaki tarih metni istediğimiz günü gösteriyor mu?

    Arayüz tarihi 2026-08-20, 20.08.2026, 20 Ağustos, Aug 20 gibi farklı
    biçimlerde yazabiliyor. Günün geçmesi ve ay ya da yıldan birinin
    doğrulanması yeterli — ikisini birden şart koşmak, yılı yazmayan
    biçimlerde doğru zamanlamayı da reddediyordu.
    """
    if not okunan:
        return False

    rakamlar = re.findall(r"\d+", okunan)
    kucuk = okunan.lower()

    gun_var = str(ne_zaman.day) in rakamlar or f"{ne_zaman.day:02d}" in rakamlar
    yil_var = str(ne_zaman.year) in rakamlar
    ay_var = (
        str(ne_zaman.month) in rakamlar
        or f"{ne_zaman.month:02d}" in rakamlar
        or ne_zaman.strftime("%b").lower() in kucuk
        or AYLAR_TR[ne_zaman.month - 1] in kucuk
    )
    return gun_var and (ay_var or yil_var)


def _zamanlama_dogrula(kok, sayfa, ne_zaman: dt.datetime) -> None:
    okunan_saat = _alan_degeri(kok, selectors.SAAT_ALANI)
    okunan_tarih = _alan_degeri(kok, selectors.TARIH_ALANI)

    saat_tamam = bool(okunan_saat) and ne_zaman.strftime("%H:%M") in okunan_saat
    tarih_tamam = _tarih_uyuyor(okunan_tarih, ne_zaman)

    if not (saat_tamam and tarih_tamam):
        dokum(sayfa, "zamanlama-kurulamadi")
        raise ZamanlamaHatasi(
            f"Zamanlama doğrulanamadı (alanlarda okunan: tarih={okunan_tarih!r}, "
            f"saat={okunan_saat!r}; beklenen: {ne_zaman:%Y-%m-%d %H:%M}). "
            "Video YAYINLANMADI — yanlışlıkla hemen paylaşılmasın diye durduruldu."
        )


def _alan_degeri(kok, secenekler: list[str]) -> str:
    alan = ilk_gorunen(kok, secenekler, timeout=3000)
    if alan is None:
        return ""
    try:
        return (alan.input_value(timeout=2000) or "").strip()
    except Exception:  # noqa: BLE001 - input değilse metnine bak
        try:
            return (alan.inner_text(timeout=2000) or "").strip()
        except Exception:  # noqa: BLE001
            return ""


def _zaman_dogrula(ne_zaman: dt.datetime) -> dt.datetime:
    if ne_zaman.tzinfo is None:
        ne_zaman = ne_zaman.replace(tzinfo=TZ)
    simdi = dt.datetime.now(TZ)
    fark = ne_zaman - simdi
    if fark < EN_ERKEN:
        raise ZamanlamaHatasi(
            f"{ne_zaman:%Y-%m-%d %H:%M} çok yakın — TikTok en az 15 dakika "
            "sonrasına zamanlamaya izin veriyor."
        )
    if fark > EN_GEC:
        raise ZamanlamaHatasi(
            f"{ne_zaman:%Y-%m-%d %H:%M} çok uzak — TikTok en fazla 10 gün "
            "sonrasına zamanlıyor. Bu postu daha yakın bir tarihte tekrar dene."
        )
    return ne_zaman


# --- Yükleme akışı -----------------------------------------------------------


def _tur_katmanini_kapat(sayfa) -> None:
    """TikTok'un tanıtım turu (react-joyride) katmanını kapatır.

    Studio bazen yükleme ekranında "yenilikleri gezdiren" bir tur açıyor;
    katman tüm tıklamaları yuttuğu için sonraki adımlar zaman aşımına
    düşüyordu (2026-08-18 CI koşusu). Katman yoksa hiçbir şey yapmaz.
    """
    # Atla düğmesi her sürümde bulunamıyor ve katman sonraki adımlarda
    # yeniden açılabiliyor (18-19.08 koşuları böyle düştü). Düğümleri DOM'dan
    # sökmek React'i "Bir şeyler ters gitti" ekranına düşürdü (20.08 koşusu,
    # döküm ekranında görüldü) — bu yüzden katman yalnızca CSS ile
    # etkisizleştiriliyor: görünmez ve tıklama geçirir, React'e dokunulmaz.
    try:
        sayfa.evaluate(
            """() => {
                if (document.getElementById('joyride-notr')) return;
                const st = document.createElement('style');
                st.id = 'joyride-notr';
                st.textContent = '#react-joyride-portal, .react-joyride__overlay,' +
                    ' [data-test-id="overlay"] {' +
                    ' pointer-events: none !important;' +
                    ' visibility: hidden !important; }';
                document.head.appendChild(st);
            }"""
        )
    except Exception:  # noqa: BLE001
        pass


def _video_yukle(kok, sayfa, yol: pathlib.Path) -> None:
    # Dosya girişi TikTok'ta tasarım geregi gizli (display:none) — gorunurluk
    # beklersek asla bulamayiz (2026-08-18'de ilk CI kosusu boyle dustu).
    # set_input_files gizli girise de calisir; DOM'a eklenmis olmasi yeter.
    giris = None
    for secici in selectors.DOSYA_GIRISI:
        aday = kok.locator(secici).first
        try:
            aday.wait_for(state="attached", timeout=10000)
            giris = aday
            break
        except Exception:  # noqa: BLE001
            continue
    if giris is None:
        # Ekran goruntusu + HTML dokumuyle birlikte hata versin.
        giris = gorunmesini_bekle(kok, selectors.DOSYA_GIRISI, "dosya seçici", sayfa=sayfa)
    giris.set_input_files(str(yol))
    print(f"  ⬆️  yükleniyor: {yol.name} ({yol.stat().st_size // 1024} KB)")
    _tur_katmanini_kapat(sayfa)

    # Büyük dosyalar dakikalar sürebiliyor; ilerleme göstergesi kaybolana kadar bekle.
    kaybolma_suresi = int(os.environ.get("TIKTOK_STUDIO_YUKLEME_TIMEOUT", "900000"))
    kaybolmasini_bekle(kok, selectors.YUKLENIYOR, timeout=kaybolma_suresi)
    gorunmesini_bekle(
        kok, selectors.YUKLEME_TAMAM, "yükleme onayı", timeout=120000, sayfa=sayfa
    )
    print("  ✅ video yüklendi")


def _yayinla(kok, sayfa, zamanlandi: bool) -> None:
    buton = gorunmesini_bekle(
        kok, selectors.YAYINLA_BUTONU, "yayınla butonu", sayfa=sayfa
    )

    # Buton, video işlenene kadar pasif kalıyor.
    for _ in range(60):
        try:
            if buton.is_enabled():
                break
        except Exception:  # noqa: BLE001
            pass
        bekle(2)
    else:
        dokum(sayfa, "yayinla-pasif")
        raise StudioError("Yayınla butonu aktifleşmedi — video işlenemedi olabilir.")

    buton.click()
    bekle(3)

    sonuc = ilk_gorunen(kok, selectors.YAYIN_TAMAM, timeout=60000)
    if sonuc is None:
        # Studio başarıda /content adresine yönlendiriyor; bu da geçerli onay.
        if "content" not in (getattr(sayfa, "url", "") or ""):
            dokum(sayfa, "yayin-onayi-yok")
            raise StudioError(
                "Yayın onayı görünmedi. Video yayınlanmış olabilir de olmayabilir de — "
                "TikTok Studio > İçerik ekranından kontrol et."
            )
    print("  🚀 " + ("zamanlandı" if zamanlandi else "yayınlandı"))


def studio_paylas(
    caption: str,
    media_path: str,
    ne_zaman: dt.datetime | None = None,
) -> str:
    """Videoyu Studio'ya yükler; `ne_zaman` verilirse o tarihe zamanlar."""
    yol = pathlib.Path(media_path)
    if not yol.exists():
        raise StudioError(f"Video dosyası bulunamadı: {yol}")

    if ne_zaman is not None:
        ne_zaman = _zaman_dogrula(ne_zaman)

    etiket = f"zamanla → {ne_zaman:%Y-%m-%d %H:%M}" if ne_zaman else "hemen yayınla"

    if config.DRY_RUN:
        print(f"  [DRY RUN] TikTok Studio ({etiket}) → {yol}")
        return "dry-run"

    with studio(selectors.YUKLEME) as page:
        _tur_katmanini_kapat(page)
        kok = yukleme_koku(page)
        _video_yukle(kok, page, yol)
        _aciklama_yaz(kok, page, caption)
        if ne_zaman is not None:
            _zamanla(kok, page, ne_zaman)
        _yayinla(kok, page, zamanlandi=ne_zaman is not None)

    return f"studio:{ne_zaman:%Y-%m-%d %H:%M}" if ne_zaman else "studio:yayinlandi"


# --- src/main.py'nin çağırdığı yayıncı ---------------------------------------


def publish(
    caption: str,
    media_path: str | None,
    is_video: bool = True,
    extra: dict | None = None,
) -> str:
    """main.py yayıncı arayüzü.

    Post'un front matter'ında `tiktok_schedule_at: 2026-08-20 10:00` varsa
    hemen yayınlamak yerine TikTok'un zamanlayıcısına bırakır.
    """
    extra = extra or {}

    if not media_path:
        raise StudioError("TikTok Studio sadece video gönderimine izin veriyor.")
    if not is_video:
        raise StudioError("TikTok için 'media' bir video dosyası olmalı (.mp4).")

    ne_zaman = None
    ham = extra.get("tiktok_schedule_at")
    if ham:
        ne_zaman = posts.parse_datetime(ham)

    try:
        return studio_paylas(caption, media_path, ne_zaman)
    except (OturumDustu, StudioError) as exc:
        if not YEDEK_API:
            raise
        print(f"  ⚠️  Studio başarısız: {exc}")
        print("  ↩️  resmî API'nin taslak moduna düşülüyor (video TikTok'ta gelen kutuna gelecek)")
        from .. import tiktok

        return tiktok.publish(caption, media_path, is_video)
