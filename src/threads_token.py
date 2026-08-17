"""Threads token'ını yeniler.

Threads'in uzun ömürlü token'ı 60 gün geçerli. Süresi dolmadan yenilenirse
sayaç yeniden 60 güne kurulur; dolarsa tools/threads_auth.py ile baştan
yetkilendirme gerekir. Bu script yenilemeyi otomatikleştirir ve ayda bir
çalışacak şekilde zamanlanır.

    python -m src.threads_token                 # yenile, yeni token'ı yaz
    python -m src.threads_token --check         # sadece geçerlilik süresini göster
    python -m src.threads_token --out token.txt # yeni token'ı bu dosyaya yaz

Yeni token'ın saklandığı yer ortama göre değişir:

  GitLab : GITLAB_TOKEN (api yetkili) + CI_PROJECT_ID varsa CI değişkeni
           doğrudan bu script tarafından güncellenir.
  GitHub : token `--out` dosyasına yazılır; workflow onu `gh secret set`
           ile secret'a aktarır (GitHub secret'ları şifreli yazıldığı için
           bu adım CLI ile yapılıyor).

Token asla ekrana basılmaz — sadece dosyaya ve secret'a yazılır.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import pathlib
import sys

import requests

from . import config

REFRESH_URL = "https://graph.threads.net/refresh_access_token"
ME_URL = f"{config.THREADS_BASE}/me"


class TokenError(RuntimeError):
    pass


def _gun(saniye) -> int:
    try:
        return int(saniye) // 86400
    except (TypeError, ValueError):
        return 0


def kontrol_et(token: str) -> None:
    """Token çalışıyor mu, hangi hesaba ait — kısa bir sağlık kontrolü."""
    response = requests.get(
        ME_URL, params={"fields": "id,username", "access_token": token}, timeout=60
    )
    payload = response.json()
    if "error" in payload:
        raise TokenError(payload["error"].get("message", str(payload["error"])))
    print(f"Token geçerli — hesap: @{payload.get('username', '?')} ({payload.get('id')})")


def yenile(token: str) -> tuple[str, int]:
    """Token'ı yeniler; (yeni_token, kalan_gun) döner."""
    response = requests.get(
        REFRESH_URL,
        params={"grant_type": "th_refresh_token", "access_token": token},
        timeout=60,
    )
    payload = response.json()
    if "access_token" not in payload:
        raise TokenError(f"Token yenilenemedi: {payload}")
    return payload["access_token"], _gun(payload.get("expires_in"))


def gitlab_degiskenini_guncelle(token: str) -> bool:
    """GitLab CI değişkenini günceller. Ortam uygun değilse False döner."""
    gitlab_token = os.environ.get("GITLAB_TOKEN", "").strip()
    project_id = os.environ.get("CI_PROJECT_ID", "").strip()
    if not (gitlab_token and project_id):
        return False

    api = os.environ.get("CI_API_V4_URL", "https://gitlab.com/api/v4").rstrip("/")
    headers = {"PRIVATE-TOKEN": gitlab_token}

    def gonder(masked: bool):
        data = {"value": token, "masked": str(masked).lower(), "protected": "false"}
        response = requests.put(
            f"{api}/projects/{project_id}/variables/THREADS_ACCESS_TOKEN",
            headers=headers, data=data, timeout=60,
        )
        if response.status_code == 404:
            # Değişken henüz yoksa oluştur.
            response = requests.post(
                f"{api}/projects/{project_id}/variables",
                headers=headers,
                data={"key": "THREADS_ACCESS_TOKEN", **data},
                timeout=60,
            )
        return response

    response = gonder(masked=True)
    if response.status_code == 400:
        # GitLab bazı karakterleri maskeleyemiyor; maskesiz yazıp uyaralım.
        print("⚠️  Token GitLab'ın maskeleme kurallarına uymadı, maskesiz yazılıyor.")
        response = gonder(masked=False)

    if response.status_code >= 300:
        raise TokenError(
            f"GitLab değişkeni güncellenemedi ({response.status_code}): {response.text[:200]}"
        )

    print("GitLab CI değişkeni güncellendi: THREADS_ACCESS_TOKEN")
    return True


def _alarm_ver(hata: str) -> None:
    """Yenileme başarısız olursa issue açar.

    Bu iş ayda bir çalıştığı için hatası kolayca gözden kaçar; fark edilmezse
    60. günde Threads paylaşımları sessizce durur. Issue, kaydı okumaya gerek
    kalmadan haber verir. Issue açılamaması yenilemeyi daha da kötü yapmasın
    diye burada hiçbir istisna yukarı taşınmıyor.
    """
    # src/marketplaces bir paket değil (__init__.py yok); diğer scriptler oraya
    # cd edip düz import ediyor. Buradan aynısını yapamayacağımız için modülü
    # doğrudan dosya yolundan yüklüyoruz.
    try:
        yol = pathlib.Path(__file__).with_name("marketplaces") / "issue_tracker.py"
        spec = importlib.util.spec_from_file_location("issue_tracker", yol)
        if spec is None or spec.loader is None:
            return
        issue_tracker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(issue_tracker)
    except Exception as exc:  # noqa: BLE001
        print(f"   (issue modülü yüklenemedi: {exc})")
        return

    govde = (
        "Threads token yenileme işi başarısız oldu.\n\n"
        f"**Hata:** {hata}\n\n"
        "Token 60 gün geçerli; yenilenemezse süre dolduğunda Threads "
        "paylaşımları durur ve `tools/threads_auth.py` ile elle yeniden "
        "yetkilendirme gerekir.\n\n"
        "Kontrol için: `JOB=threads-token`, `EXTRA_ARGS=--check` ile bir "
        "pipeline çalıştır.\n\n"
        "_Bu issue `src/threads_token.py` tarafından açıldı._"
    )
    try:
        issue_tracker.upsert_issue(
            "Threads token yenilenemedi", govde, ["threads", "token"]
        )
    except Exception as exc:  # noqa: BLE001
        print(f"   (issue açılamadı: {exc})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Threads token yenileme")
    parser.add_argument("--check", action="store_true", help="Yenileme, sadece kontrol et")
    parser.add_argument("--out", default="", help="Yeni token'ın yazılacağı dosya")
    args = parser.parse_args()

    token = config.THREADS_TOKEN
    if not token:
        print("THREADS_ACCESS_TOKEN tanımlı değil — Threads yenilemesi atlandı.")
        sys.exit(0)

    try:
        kontrol_et(token)
        if args.check:
            return

        yeni, kalan = yenile(token)
        print(f"Token yenilendi — {kalan} gün daha geçerli.")

        yazildi = gitlab_degiskenini_guncelle(yeni)

        if args.out:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(yeni)
            print(f"Yeni token dosyaya yazıldı: {args.out}")
            yazildi = True

        if not yazildi:
            print(
                "\n⚠️  Yeni token hiçbir yere kaydedilmedi. --out ile bir dosyaya yaz\n"
                "   ya da GITLAB_TOKEN tanımla; yoksa 60 gün sonra yeniden\n"
                "   yetkilendirme gerekecek."
            )
    except TokenError as exc:
        print(f"❌ {exc}")
        print("   Token süresi dolmuşsa: python tools/threads_auth.py ile yeniden üret.")
        _alarm_ver(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
