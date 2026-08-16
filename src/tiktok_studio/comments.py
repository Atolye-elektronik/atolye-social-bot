"""TikTok Studio'daki yorumları toplar ve yanıt taslağı üretir.

Yorumlar ekrandan okunuyor. Ağ dinlemesi de denendi ama Studio yorum listesini
ayrı bir JSON ucundan çekmiyor; ekrandaki yapı ise düzenli ve okunabilir.

Bilinçli sınır: bu modül yorum GÖNDERMİYOR. Yorumları toplayıp
`content/yorum_taslaklari.md` dosyasına "şu yoruma şu yanıt" biçiminde
taslak yazıyor; göndermeye sen karar veriyorsun. Sebebi basit — hesabın
adına herkese açık konuşan bir otomasyonun yanlış cevabı, kaçırılmış bir
yorumdan çok daha pahalıya patlıyor.

Yanıt eşlemesi `content/yorum_yanitlari.json` dosyasında. Anahtar kelimeler
yoruma denk gelirse ilgili hazır yanıt taslağa yazılıyor; hiçbiri tutmazsa
yorum "elle yanıtla" listesine düşüyor.

    python -m src.tiktok_studio yorumlar
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re

from . import selectors
from .session import bekle, dokum, ilk_gorunen, studio

KAYIT = pathlib.Path("state/tiktok_comments.json")
TASLAK = pathlib.Path("content/yorum_taslaklari.md")
YANITLAR = pathlib.Path("content/yorum_yanitlari.json")

# Bir çalışmada en fazla kaç yorum sayfası taransın.
SAYFA_SINIRI = 5


def _yanit_kurallari() -> list[dict]:
    if not YANITLAR.exists():
        return []
    try:
        veri = json.loads(YANITLAR.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{YANITLAR} okunamadı: {exc}") from exc
    return veri.get("kurallar", [])


def _yanit_bul(metin: str, kurallar: list[dict]) -> str | None:
    duz = metin.lower()
    for kural in kurallar:
        for kelime in kural.get("anahtarlar", []):
            if kelime.lower() in duz:
                return kural.get("yanit")
    return None


# --- Toplama -----------------------------------------------------------------


def _domdan_yorumlar(page) -> dict:
    """Yorumları ekrandan okur.

    TikTok yorumlara kalıcı bir kimlik göstermediği için anahtarı yazar +
    metinden üretiyoruz; aynı yorum ikinci çalıştırmada "yeni" sayılmasın diye
    bu yeterli.
    """
    try:
        ham = page.evaluate(selectors.YORUM_OKUYUCU_JS)
    except Exception:  # noqa: BLE001 - sayfa henüz hazır değilse
        return {}

    toplanan: dict = {}
    for yorum in ham or []:
        metin = (yorum.get("metin") or "").strip()
        if not metin:
            continue
        yazar = (yorum.get("yazar") or "").strip()
        anahtar = re.sub(r"\W+", "", f"{yazar}-{metin}")[:60].lower()
        try:
            begeni = int(re.sub(r"\D", "", yorum.get("begeni") or "0") or 0)
        except ValueError:
            begeni = 0
        toplanan[anahtar] = {
            "metin": metin,
            "yazar": yazar,
            "begeni": begeni,
            "zaman": (yorum.get("zaman") or "").strip(),
        }
    return toplanan


def topla() -> dict:
    """Yorum sayfasını gezip yorumları döndürür."""
    with studio(selectors.YORUMLAR) as page:
        bekle(9)

        # "Daha fazla" varsa birkaç sayfa daha aç.
        for _ in range(SAYFA_SINIRI):
            daha = ilk_gorunen(page, selectors.DAHA_FAZLA_YORUM, timeout=3000)
            if daha is None:
                break
            daha.click()
            bekle(3)

        toplanan = _domdan_yorumlar(page)

        if not toplanan:
            dokum(page, "yorum-bos")
            print("⚠️  Hiç yorum okunamadı — yeni yorum yoksa bu normal.")

    return toplanan


# --- Kayıt ve taslak ---------------------------------------------------------


def _gecmis() -> dict:
    if not KAYIT.exists():
        return {}
    try:
        return json.loads(KAYIT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def calistir() -> int:
    kurallar = _yanit_kurallari()
    gecmis = _gecmis()
    toplanan = topla()

    yeniler = {k: v for k, v in toplanan.items() if k not in gecmis}
    for kimlik, yorum in yeniler.items():
        yorum["gorulme"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        gecmis[kimlik] = yorum

    KAYIT.parent.mkdir(parents=True, exist_ok=True)
    KAYIT.write_text(
        json.dumps(gecmis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Toplam {len(toplanan)} yorum okundu, {len(yeniler)} tanesi yeni.")
    if not yeniler:
        return 0

    hazir, elle = [], []
    for kimlik, yorum in yeniler.items():
        yanit = _yanit_bul(yorum["metin"], kurallar)
        (hazir if yanit else elle).append((kimlik, yorum, yanit))

    satirlar = [
        "# TikTok yorum yanıt taslakları",
        "",
        f"Üretim: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "Bu dosya otomatik üretildi. Yanıtlar **gönderilmedi** — uygun",
        "bulduklarını TikTok Studio > Yorumlar ekranından kopyalayıp yapıştır.",
        "",
    ]

    if hazir:
        satirlar += ["## Hazır yanıtı olanlar", ""]
        for _, yorum, yanit in hazir:
            yazar = f"@{yorum['yazar']}" if yorum["yazar"] else "(bilinmeyen)"
            satirlar += [
                f"**{yazar}:** {yorum['metin']}",
                "",
                f"> {yanit}",
                "",
                "---",
                "",
            ]

    if elle:
        satirlar += ["## Elle yanıtlaman gerekenler", ""]
        for _, yorum, _ in elle:
            yazar = f"@{yorum['yazar']}" if yorum["yazar"] else "(bilinmeyen)"
            satirlar += [f"- **{yazar}:** {yorum['metin']}"]
        satirlar += [
            "",
            f"Sık tekrarlayan bir soru varsa `{YANITLAR}` dosyasına kural ekle,",
            "bir dahakine hazır yanıt üretilsin.",
            "",
        ]

    TASLAK.parent.mkdir(parents=True, exist_ok=True)
    TASLAK.write_text("\n".join(satirlar), encoding="utf-8")

    print(f"  {len(hazir)} yoruma hazır yanıt, {len(elle)} yorum elle yanıt bekliyor.")
    print(f"Taslak: {TASLAK}")
    return 0
