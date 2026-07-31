"""TikTok için bir kerelik yetkilendirme — refresh token üretir.

Bu scripti KENDİ BİLGİSAYARINDA çalıştır, GitHub Actions'ta değil.

    pip install requests
    export TIKTOK_CLIENT_KEY=...
    export TIKTOK_CLIENT_SECRET=...
    python tools/tiktok_auth.py

Script sana bir bağlantı verir. Bağlantıyı tarayıcıda açıp TikTok
hesabınla giriş yaparsın, TikTok seni geri yönlendirir. Adres
çubuğundaki 'code=' değerini kopyalayıp scripte yapıştırırsın.
Script sana bir refresh token verir — onu GitHub Secrets'a
TIKTOK_REFRESH_TOKEN adıyla eklersin.

Not: TikTok panelinde Redirect URI olarak aşağıdaki adresi
tanımlamış olman gerekiyor:
    https://atolyeelektronik.com/tiktok/callback
"""

from __future__ import annotations

import os
import urllib.parse

import requests

CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "").strip()
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.environ.get(
    "TIKTOK_REDIRECT_URI", "https://atolyeelektronik.com/tiktok/callback"
).strip()

SCOPES = "user.info.basic,video.upload,video.publish"


def main() -> None:
    if not (CLIENT_KEY and CLIENT_SECRET):
        raise SystemExit("TIKTOK_CLIENT_KEY ve TIKTOK_CLIENT_SECRET tanımlı olmalı.")

    params = {
        "client_key": CLIENT_KEY,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": "atolye",
    }
    auth_url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)

    print("\n1) Aşağıdaki bağlantıyı tarayıcında aç ve TikTok hesabınla izin ver:\n")
    print(auth_url)
    print("\n2) Yönlendirildiğin adresteki 'code=' değerini kopyala.")
    print("   (Sayfa açılmasa bile adres çubuğundaki code yeterli.)\n")

    code = input("code = ").strip()
    if "code=" in code:
        code = urllib.parse.parse_qs(urllib.parse.urlparse(code).query).get("code", [code])[0]
    code = urllib.parse.unquote(code)

    response = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=60,
    )
    payload = response.json()

    if "refresh_token" not in payload:
        raise SystemExit(f"Token alınamadı:\n{payload}")

    print("\n✅ Başarılı. Aşağıdaki değeri GitHub Secrets'a ekle:\n")
    print("  Ad   : TIKTOK_REFRESH_TOKEN")
    print(f"  Değer: {payload['refresh_token']}")
    print(f"\n(open_id: {payload.get('open_id')}, geçerlilik: {payload.get('refresh_expires_in')} sn)")
    print("\nBu değeri kimseyle paylaşma.")


if __name__ == "__main__":
    main()
