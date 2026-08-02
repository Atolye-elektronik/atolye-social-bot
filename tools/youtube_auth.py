"""YouTube icin bir kerelik yetkilendirme — refresh token uretir.

Bu scripti KENDI BILGISAYARINDA calistir, GitHub Actions'ta degil.

Hazirlik (bir kere):
  1. console.cloud.google.com adresinde yeni bir proje olustur.
  2. "APIs & Services" > "Library" > "YouTube Data API v3" > Enable.
  3. "APIs & Services" > "OAuth consent screen": External, uygulama adi ve
     e-posta gir. Test users bolumune kendi Google hesabini ekle.
  4. "Credentials" > "Create credentials" > "OAuth client ID" >
     Application type: **Desktop app**. Client ID ve Client secret'i not al.

Calistirma:
  pip install requests
  export YOUTUBE_CLIENT_ID=...
  export YOUTUBE_CLIENT_SECRET=...
  python tools/youtube_auth.py

Script sana bir baglanti verir. Tarayicida acip Google hesabinla izin
verirsin, ekranda cikan kodu buraya yapistirirsin. Sonunda bir refresh
token alirsin; onu GitHub Secrets'a YOUTUBE_REFRESH_TOKEN adiyla ekle.
"""

from __future__ import annotations

import os
import urllib.parse

import requests

CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
REDIRECT = "urn:ietf:wg:oauth:2.0:oob"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def main() -> None:
    if not (CLIENT_ID and CLIENT_SECRET):
        raise SystemExit("YOUTUBE_CLIENT_ID ve YOUTUBE_CLIENT_SECRET tanimli olmali.")

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)

    print("\n1) Asagidaki baglantiyi tarayicinda ac ve Google hesabinla izin ver:\n")
    print(url)
    print("\n2) Ekranda cikan kodu kopyala.\n")

    code = input("kod = ").strip()

    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT,
        },
        timeout=60,
    )
    payload = r.json()
    if "refresh_token" not in payload:
        raise SystemExit(f"Token alinamadi:\n{payload}")

    print("\nBasarili. Asagidaki degeri GitHub Secrets'a ekle:\n")
    print("  Ad   : YOUTUBE_REFRESH_TOKEN")
    print(f"  Deger: {payload['refresh_token']}")
    print("\nBu degeri kimseyle paylasma.")


if __name__ == "__main__":
    main()
