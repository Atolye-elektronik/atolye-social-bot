"""Threads için bir kerelik yetkilendirme — uzun ömürlü token üretir.

Bu scripti KENDİ BİLGİSAYARINDA çalıştır, CI içinde değil.

    pip install requests
    export THREADS_APP_ID=...
    export THREADS_APP_SECRET=...
    python tools/threads_auth.py

Öncesinde Meta App Dashboard'da yapman gerekenler:

  1. developers.facebook.com → uygulamana **Threads API** ürününü ekle.
     (Facebook/Instagram ürünlerinden ayrı bir üründür.)
  2. Use case olarak "Access the Threads API" → izinler:
        threads_basic
        threads_content_publish
  3. Redirect Callback URI olarak şunu tanımla (aşağıdakiyle birebir aynı):
        https://atolyeelektronik.com/threads/callback
     Farklı bir adres kullanacaksan THREADS_REDIRECT_URI ile geç.
  4. Threads hesabını uygulamaya test/kullanıcı olarak ekle.

App ID/Secret'ı Threads ürününün kendi ekranından al — bunlar Facebook
uygulamasının App ID'sinden farklı olabilir.

Script sonunda iki değer verir; ikisini de repo secret'larına ekle:
    THREADS_ACCESS_TOKEN   (60 gün geçerli, otomatik yenilenir)
    THREADS_USER_ID
"""

from __future__ import annotations

import os
import urllib.parse

import requests

APP_ID = os.environ.get("THREADS_APP_ID", "").strip()
APP_SECRET = os.environ.get("THREADS_APP_SECRET", "").strip()
REDIRECT_URI = os.environ.get(
    "THREADS_REDIRECT_URI", "https://atolyeelektronik.com/threads/callback"
).strip()

SCOPES = "threads_basic,threads_content_publish"

AUTH_URL = "https://threads.net/oauth/authorize"
TOKEN_URL = "https://graph.threads.net/oauth/access_token"
EXCHANGE_URL = "https://graph.threads.net/access_token"


def main() -> None:
    if not (APP_ID and APP_SECRET):
        raise SystemExit("THREADS_APP_ID ve THREADS_APP_SECRET tanımlı olmalı.")

    params = {
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "response_type": "code",
    }
    print("\n1) Aşağıdaki bağlantıyı tarayıcında aç ve Threads hesabınla izin ver:\n")
    print(f"{AUTH_URL}?{urllib.parse.urlencode(params)}")
    print("\n2) Yönlendirildiğin adresteki 'code=' değerini kopyala.")
    print("   (Sayfa açılmasa bile adres çubuğundaki code yeterli.)")
    print("   Not: Threads kodun sonuna '#_' ekliyor, onu atman gerek —")
    print("   script zaten kendisi temizliyor.\n")

    code = input("code = ").strip()
    if "code=" in code:
        code = urllib.parse.parse_qs(urllib.parse.urlparse(code).query).get("code", [code])[0]
    code = urllib.parse.unquote(code).split("#")[0]

    # 1) Kod → kısa ömürlü token (1 saat)
    short = requests.post(
        TOKEN_URL,
        data={
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=60,
    ).json()

    if "access_token" not in short:
        raise SystemExit(f"Token alınamadı:\n{short}")

    user_id = str(short.get("user_id", ""))

    # 2) Kısa ömürlü → uzun ömürlü token (60 gün)
    long_lived = requests.get(
        EXCHANGE_URL,
        params={
            "grant_type": "th_exchange_token",
            "client_secret": APP_SECRET,
            "access_token": short["access_token"],
        },
        timeout=60,
    ).json()

    if "access_token" not in long_lived:
        raise SystemExit(f"Uzun ömürlü token alınamadı:\n{long_lived}")

    token = long_lived["access_token"]
    gecerlilik = int(long_lived.get("expires_in", 0)) // 86400

    if not user_id:
        me = requests.get(
            "https://graph.threads.net/v1.0/me",
            params={"fields": "id,username", "access_token": token},
            timeout=60,
        ).json()
        user_id = str(me.get("id", ""))

    print("\n✅ Başarılı. Aşağıdaki iki değeri repo secret'larına ekle:\n")
    print("  Ad   : THREADS_ACCESS_TOKEN")
    print(f"  Değer: {token}\n")
    print("  Ad   : THREADS_USER_ID")
    print(f"  Değer: {user_id}")
    print(f"\n(Geçerlilik: {gecerlilik} gün — token yenileme akışı bunu otomatik uzatır.)")
    print("\nBu değerleri kimseyle paylaşma.")


if __name__ == "__main__":
    main()
