"""YouTube icin bir kerelik yetkilendirme - refresh token uretir.

Bu scripti KENDI BILGISAYARINDA calistir, GitHub Actions'ta degil.

NOT: Google'in eski "kodu ekranda goster" yontemi (urn:ietf:wg:oauth:2.0:oob)
31 Ocak 2023'te tamamen kapatildi. Bu script artik loopback (localhost)
yontemini kullaniyor: kendi bilgisayarinda kisa sureligine bir web sunucu
acar, Google izin verdikten sonra tarayici kodu oraya birakir.

Hazirlik (bir kere):
  1. console.cloud.google.com adresinde yeni bir proje olustur.
  2. "APIs & Services" > "Library" > "YouTube Data API v3" > Enable.
  3. "APIs & Services" > "OAuth consent screen": External sec, uygulama adi ve
     e-posta gir. "Test users" bolumune kanalin sahibi Google hesabini ekle.
     ONEMLI: Yayin durumunu "In production" yap. "Testing" kalirsa Google
     refresh token'i 7 gun sonra iptal ediyor ve bot durur. Dogrulanmamis
     uygulama uyarisi cikar; "Gelismis > ... uygulamasina git" ile gecilir.
  4. "Credentials" > "Create credentials" > "OAuth client ID" >
     Application type: **Desktop app**. Client ID ve Client secret'i not al.

Calistirma:
  pip install requests
  export YOUTUBE_CLIENT_ID=...
  export YOUTUBE_CLIENT_SECRET=...
  python tools/youtube_auth.py

Script tarayicini acar. Izin verdikten sonra "Yetkilendirme tamamlandi"
yazisini gorursun. Terminalde cikan refresh token'i GitHub Secrets'a
YOUTUBE_REFRESH_TOKEN adiyla ekle.
"""

from __future__ import annotations

import http.server
import os
import socket
import threading
import time
import urllib.parse
import webbrowser

import requests

CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
SCOPE = (
    "https://www.googleapis.com/auth/youtube.upload "
    "https://www.googleapis.com/auth/youtube.force-ssl"
)

_kod: dict[str, str] = {}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        sorgu = urllib.parse.urlparse(self.path).query
        alanlar = urllib.parse.parse_qs(sorgu)
        if "code" in alanlar:
            _kod["code"] = alanlar["code"][0]
            mesaj = "Yetkilendirme tamamlandi. Bu sekmeyi kapatabilirsin."
        else:
            _kod["error"] = alanlar.get("error", ["bilinmeyen hata"])[0]
            mesaj = f"Hata: {_kod['error']}"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            f"<html><body style='font-family:sans-serif;padding:40px'>"
            f"<h2>{mesaj}</h2></body></html>".encode("utf-8")
        )

    def log_message(self, *args) -> None:  # sessiz kal
        pass


def _bos_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    if not (CLIENT_ID and CLIENT_SECRET):
        raise SystemExit("YOUTUBE_CLIENT_ID ve YOUTUBE_CLIENT_SECRET tanimli olmali.")

    port = _bos_port()
    redirect = f"http://localhost:{port}"

    sunucu = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=sunucu.handle_request, daemon=True).start()

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)

    print("\nTarayicida su adres aciliyor (acilmazsa elle kopyala):\n")
    print(url + "\n")
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass

    print("Izin vermeni bekliyorum...")
    for _ in range(600):          # en fazla 5 dakika bekle
        if _kod:
            break
        time.sleep(0.5)

    if "code" not in _kod:
        raise SystemExit(f"Yetkilendirme basarisiz: {_kod.get('error', 'zaman asimi')}")

    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": _kod["code"],
            "grant_type": "authorization_code",
            "redirect_uri": redirect,
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
