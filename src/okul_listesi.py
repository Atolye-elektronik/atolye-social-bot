"""MEB kurum dizininden meslek liselerinin listesini çıkarır.

Kaynak, MEB'in herkese açık okul bağlantıları dizini
(meb.gov.tr/baglantilar/okullar). Dizin her okul için adını, web sitesi
alt alanını ve `il/ilçe/kurum_kodu` biçiminde bir yol veriyor. Okulların
kurumsal e-postası da kurum kodundan türüyor: `{kurum_kodu}@meb.k12.tr`.

Çıktı, `src/okul_daveti.py` betiğinin beklediği `okul,bolum,eposta`
sütunlarını içerir; yani liste doğrudan gönderime hazırdır.

Kullanımı:
    python -m src.okul_listesi --il 7                 # sadece Antalya
    python -m src.okul_listesi --il 1,6,7,34,35       # birkaç il
    python -m src.okul_listesi                        # 81 il
    python -m src.okul_listesi --tur mesem            # meslekî eğitim merkezleri
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import re
import sys
import time

import requests

AJAX = "https://www.meb.gov.tr/baglantilar/okullar/okullar_ajax.php"

# Dizinde arama kutusuna yazılan metin. Okul türünü bu belirliyor.
TURLER = {
    "mtal": "mesleki ve teknik anadolu lisesi",
    "mesem": "mesleki eğitim merkezi",
    # BİLSEM'ler üstün yetenekli öğrenciler için robotik/kodlama atölyesi
    # işletiyor ve bütçeleriyle malzeme alıyorlar.
    "bilsem": "bilim ve sanat merkezi",
}

IL_SAYISI = 81
BEKLEME = 1.0

# Adında bu kelimeler geçen okullar belirli bir sektöre odaklı; elektrik-elektronik
# atölyesi olma ihtimalleri düşük. Listeden atmıyoruz, sadece işaretliyoruz ki
# kampanyaya kimden başlayacağın belli olsun.
DAR_ALAN = (
    "ticaret", "turizm", "otelcilik", "tarım", "sağlık", "anadolu sağlık",
    "kız", "imam hatip", "denizcilik", "uçak", "havacılık", "adalet",
    "güzel sanatlar", "spor", "moda", "tekstil", "matbaa", "gıda",
)


def _istek_govdesi(il: int, arama: str, start: int, length: int) -> list[tuple[str, str]]:
    alanlar = [
        ("draw", "1"),
        ("start", str(start)),
        ("length", str(length)),
        ("search[value]", arama),
        ("search[regex]", "false"),
        ("order[0][column]", "0"),
        ("order[0][dir]", "asc"),
        ("il", str(il)),
        ("ilce", "0"),
    ]
    # Dizin üç sütunlu bir DataTables tablosu; eksik sütun gönderilirse 500 dönüyor.
    for sira in range(3):
        alanlar += [
            (f"columns[{sira}][data]", "OKUL_ADI"),
            (f"columns[{sira}][name]", ""),
            (f"columns[{sira}][searchable]", "true"),
            (f"columns[{sira}][orderable]", "true"),
            (f"columns[{sira}][search][value]", ""),
            (f"columns[{sira}][search][regex]", "false"),
        ]
    return alanlar


def il_okullari(oturum: requests.Session, il: int, arama: str) -> list[dict]:
    """Tek bir ilin okullarını sayfalayarak toplar."""
    toplanan: list[dict] = []
    start, length = 0, 500

    while True:
        yanit = oturum.post(
            AJAX,
            data=_istek_govdesi(il, arama, start, length),
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"https://www.meb.gov.tr/baglantilar/okullar/index.php?ILKODU={il}",
            },
            timeout=60,
        )
        yanit.raise_for_status()
        govde = yanit.json()

        satirlar = govde.get("data", [])
        toplanan += satirlar

        toplam = govde.get("recordsFiltered", 0)
        start += length
        if start >= toplam or not satirlar:
            return toplanan

        time.sleep(BEKLEME)


def ayikla(satir: dict) -> dict | None:
    """Dizin kaydını kullanılabilir alanlara böler."""
    ham = (satir.get("OKUL_ADI") or "").strip()
    yol = (satir.get("YOL") or "").strip()
    host = (satir.get("HOST") or "").strip()

    # "ANTALYA - AKSU - Aksu ... Lisesi"
    parcalar = [p.strip() for p in ham.split(" - ", 2)]
    if len(parcalar) != 3 or not host:
        return None
    il, ilce, okul = parcalar

    # "07/16/761554" -> kurum kodu son parça
    kurum_kodu = yol.split("/")[-1] if yol else ""
    if not re.fullmatch(r"\d{4,9}", kurum_kodu):
        return None

    dusuk = okul.lower()
    return {
        "il": il,
        "ilce": ilce,
        "okul": okul,
        "bolum": "",  # dizin bölüm bilgisi vermiyor; e-postada iletilmesi rica ediliyor
        "eposta": f"{kurum_kodu}@meb.k12.tr",
        "site": f"https://{host}.meb.k12.tr",
        "kurum_kodu": kurum_kodu,
        "oncelik": "dar alan" if any(k in dusuk for k in DAR_ALAN) else "genel",
    }


def topla(iller: list[int], tur: str) -> list[dict]:
    arama = TURLER[tur]
    oturum = requests.Session()
    oturum.headers["User-Agent"] = "atolye-social-bot okul listesi"

    okullar: list[dict] = []
    for sira, il in enumerate(iller, start=1):
        try:
            ham = il_okullari(oturum, il, arama)
        except (requests.RequestException, ValueError) as hata:
            # Tek il patlarsa tüm taramayı düşürme.
            print(f"  [{sira}/{len(iller)}] il {il} atlandı: {hata}", file=sys.stderr)
            continue

        temiz = [k for k in (ayikla(s) for s in ham) if k]
        okullar += temiz
        il_adi = temiz[0]["il"] if temiz else f"il {il}"
        print(f"  [{sira}/{len(iller)}] {il_adi}: {len(temiz)} okul")

        if sira < len(iller):
            time.sleep(BEKLEME)

    return okullar


def yaz(okullar: list[dict], hedef: pathlib.Path) -> None:
    hedef.parent.mkdir(parents=True, exist_ok=True)
    sutunlar = ["okul", "bolum", "eposta", "il", "ilce", "site", "kurum_kodu", "oncelik"]
    with hedef.open("w", encoding="utf-8", newline="") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=sutunlar)
        yazici.writeheader()
        yazici.writerows(okullar)


def main() -> None:
    parser = argparse.ArgumentParser(description="MEB dizininden meslek lisesi listesi çıkar")
    parser.add_argument("--il", help="İl kodu ya da virgülle ayrılmış kodlar (boşsa 81 il)")
    parser.add_argument("--tur", choices=sorted(TURLER), default="mtal")
    parser.add_argument("--cikti", type=pathlib.Path, default=pathlib.Path("pazarlama/okullar.csv"))
    args = parser.parse_args()

    iller = (
        [int(p) for p in args.il.split(",") if p.strip()]
        if args.il
        else list(range(1, IL_SAYISI + 1))
    )

    print(f"{len(iller)} il taranıyor ({TURLER[args.tur]})...")
    okullar = topla(iller, args.tur)

    # Aynı okul iki ilde görünmez ama kurum kodu üzerinden yine de tekilleştirelim.
    tekil = list({o["kurum_kodu"]: o for o in okullar}.values())
    tekil.sort(key=lambda o: (o["il"], o["ilce"], o["okul"]))

    yaz(tekil, args.cikti)
    genel = sum(1 for o in tekil if o["oncelik"] == "genel")
    print(f"\nToplam {len(tekil)} okul yazıldı: {args.cikti}")
    print(f"  {genel} tanesi genel meslek lisesi (önce bunlara git)")
    print(f"  {len(tekil) - genel} tanesi dar alan (ticaret, turizm, sağlık...)")


if __name__ == "__main__":
    main()
