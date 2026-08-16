"""TikTok Studio için bir kerelik giriş — CI'ın kullanacağı çerezi üretir.

Bu scripti KENDİ BİLGİSAYARINDA çalıştır, CI'da değil.

    pip install playwright
    python -m playwright install chromium
    python tools/tiktok_studio_login.py

Bir tarayıcı penceresi açılır. TikTok'a normal şekilde giriş yaparsın
(şifre, doğrulama kodu, ne gerekiyorsa — script hiçbirine karışmaz).
Giriş tamamlandığında script bunu kendisi algılar, çerezleri kaydeder ve
tarayıcıyı kapatır; terminale dönmene gerek yok.

Script iki şey üretir:

  .tiktok_studio_state.json   — yerel çalıştırmalar bunu kullanır (git'e girmez)
  cerez.b64                   — CI secret'ına yapıştıracağın base64 değer

Secret adı: TIKTOK_STUDIO_COOKIES
  GitHub → Settings > Secrets and variables > Actions > New repository secret
  GitLab → Settings > CI/CD > Variables (Masked + Protected işaretle)

Çerez ömrü: TikTok oturumu genelde birkaç hafta dayanır. Düştüğünde CI işi
"TikTok Studio oturumu düşmüş" diyerek durur ve bu scripti tekrar
çalıştırman gerekir. Günlük sağlık kontrolü işi, düşmeden bir hafta önce
seni uyarır.
"""

from __future__ import annotations

import base64
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.tiktok_studio import selectors, session  # noqa: E402

CIKTI_B64 = pathlib.Path("cerez.b64")

# Girişin tamamlanmasını kaç dakika bekleyelim (doğrulama kodu, şifre
# hatırlama derken uzayabiliyor).
BEKLEME_DAKIKA = 15


def _girisi_bekle(context, dakika: int = BEKLEME_DAKIKA) -> bool:
    """Oturum çerezi düşene kadar bekler.

    Terminalde Enter beklemek yerine girişi kendimiz algılıyoruz: script
    başka bir yerden (örneğin bir asistan tarafından) başlatıldığında
    kullanıcının basacağı bir terminal olmayabiliyor.
    """
    bitis = time.time() + dakika * 60
    son_bilgi = 0.0

    while time.time() < bitis:
        try:
            cerezler = {c.get("name") for c in context.cookies()}
        except Exception:  # noqa: BLE001 - tarayıcı kapatılmış olabilir
            return False

        if {"sessionid", "sessionid_ss"} & cerezler:
            # Çerez düştü; TikTok'un kalan çerezleri de yazması için biraz bekle.
            print("✅ Giriş algılandı, oturum kaydediliyor...")
            time.sleep(5)
            return True

        if time.time() - son_bilgi > 30:
            kalan = int((bitis - time.time()) / 60)
            print(f"   ...giriş bekleniyor ({kalan} dakika kaldı)")
            son_bilgi = time.time()
        time.sleep(2)

    return False


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            "Playwright kurulu değil:\n"
            "    pip install playwright\n"
            "    python -m playwright install chromium"
        )

    print("Tarayıcı açılıyor — TikTok'a giriş yap, sonra buraya dön.\n")

    with sync_playwright() as p:
        # Kanal seçimi ve yedeğe düşme mantığı session'da; burada tekrarlamıyoruz.
        browser = session.tarayici_ac(p, headless=False)
        context = browser.new_context(
            user_agent=session.TARAYICI_UA,
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        page.goto(selectors.ANASAYFA)

        print("1) Açılan pencerede TikTok hesabınla giriş yap.")
        print("2) Giriş tamamlanınca script bunu kendisi anlar ve kapanır.\n")

        if not _girisi_bekle(context):
            browser.close()
            raise SystemExit(
                "Giriş algılanamadı (süre doldu ya da tarayıcı kapatıldı). "
                "Scripti tekrar çalıştır."
            )

        state = context.storage_state()
        context.close()
        browser.close()

    isimler = {c.get("name") for c in state.get("cookies", [])}
    if not ({"sessionid", "sessionid_ss"} & isimler):
        raise SystemExit(
            "Oturum çerezi bulunamadı — giriş tamamlanmamış görünüyor. "
            "Scripti tekrar çalıştır."
        )

    session.storage_state_yaz(state)
    b64 = base64.b64encode(
        json.dumps(state, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    CIKTI_B64.write_text(b64, encoding="ascii")

    son = session.cerez_son_kullanma(state)

    print(f"\n✅ Oturum kaydedildi: {session.STATE_PATH}")
    if son:
        print(f"   Geçerlilik: {son:%Y-%m-%d %H:%M} UTC")
    print(f"\n📋 CI secret'ı için base64 değer: {CIKTI_B64} ({len(b64)} karakter)")
    print("   Secret adı: TIKTOK_STUDIO_COOKIES")
    print("\n⚠️  Bu dosya hesabına tam erişim demek. Secret'a yapıştırdıktan sonra sil:")
    print(f"   del {CIKTI_B64}")


if __name__ == "__main__":
    main()
