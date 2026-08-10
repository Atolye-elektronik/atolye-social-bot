"""Okulların hangi alanlarda (bölümlerde) eğitim verdiğini tespit eder.

MEB'in kurum dizini bölüm bilgisi vermiyor, MTEGM'nin alan/dal sayfası da
dışarıya kapalı. Ama her okulun kendi sitesinde bir site haritası var
(`/tema/siteharitasi.php`) ve alanlar orada bağlantı metni olarak listeleniyor:
"ELEKTRİK-ELEKTRONİK TEKNOLOJİSİ ALANI", "BİLİŞİM TEKNOLOJİLERİ ALANI" gibi.

Sadece site haritasına bakıyoruz; ana sayfa metnine bakmak yanıltıyor çünkü
MEB'in altbilgisinde her okulda "MEB Bilişim Sistemleri" ve "Eğitim Bilişim
Ağı" bağlantıları geçiyor ve bunlar okulun bölümü sanılıyor.

Bölümü tespit edilemeyen okul "yok" değil "bilinmiyor" olarak işaretlenir —
sitesi olmayan ya da site haritasını doldurmamış okullar var.

Kullanımı:
    python -m src.okul_bolum --liste pazarlama/okullar.csv --il ANTALYA
    python -m src.okul_bolum --liste pazarlama/okullar.csv
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import pathlib
import re
import threading

import requests

UA = "Mozilla/5.0 (compatible; atolye-social-bot/1.0)"
HARITA = "/tema/siteharitasi.php"
EK_SUTUNLAR = ["bolumler", "elektrik_elektronik", "bilisim"]

_kilit = threading.Lock()

# Türkçe karakterleri sadeleştirip büyük/küçük farkını kaldırır; okullar alan
# adlarını "ELEKTRIK", "Elektrik", "ELEKTRİK" gibi farklı yazıyor.
_ESLEME = str.maketrans("ıİşŞğĞüÜöÖçÇâÂîÎûÛ", "iissgguuooccaaiiuu")


def sadelestir(metin: str) -> str:
    return re.sub(r"\s+", " ", metin.translate(_ESLEME).lower()).strip()


def alanlari_ayikla(html: str) -> list[str]:
    """Site haritasındaki bağlantı metinlerinden alan adlarını toplar."""
    alanlar: list[str] = []
    for eslesme in re.finditer(r"<a[^>]*>(.*?)</a>", html, re.S | re.I):
        metin = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", eslesme.group(1))).strip()
        # Alan sayfalarının başlığı "... ALANI" ile bitiyor.
        if 6 < len(metin) < 90 and re.search(r"\balani\b", sadelestir(metin)):
            temiz = re.sub(r"(?i)\s*alani\s*$", "", metin).strip(" -–—:")
            if temiz and temiz.lower() not in ("alanlarimiz", "alanlarımız"):
                alanlar.append(temiz)
    # Sırayı koruyarak tekilleştir
    return list(dict.fromkeys(alanlar))


def okulu_incele(okul: dict, oturum: requests.Session) -> dict:
    try:
        yanit = oturum.get(okul["site"] + HARITA, timeout=20, headers={"User-Agent": UA})
        html = yanit.text if yanit.ok else ""
    except requests.RequestException:
        html = ""

    alanlar = alanlari_ayikla(html) if html else []

    if not alanlar:
        okul["bolumler"] = ""
        okul["elektrik_elektronik"] = "bilinmiyor"
        okul["bilisim"] = "bilinmiyor"
        return okul

    duz = sadelestir(" | ".join(alanlar))
    okul["bolumler"] = " | ".join(alanlar)
    okul["elektrik_elektronik"] = "var" if ("elektrik" in duz and "elektronik" in duz) else "yok"
    okul["bilisim"] = "var" if "bilisim" in duz else "yok"
    return okul


def calistir(liste: pathlib.Path, il: str | None = None, isci: int = 10) -> int:
    with liste.open(encoding="utf-8", newline="") as dosya:
        okullar = list(csv.DictReader(dosya))

    for okul in okullar:
        for sutun in EK_SUTUNLAR:
            okul.setdefault(sutun, "")

    hedefler = [
        o for o in okullar
        if not o.get("elektrik_elektronik")
        and o.get("site")
        and (not il or o.get("il", "").upper() == il.upper())
    ]
    if not hedefler:
        print("İncelenecek yeni okul yok.")
        return 0

    print(f"{len(hedefler)} okulun site haritasına bakılıyor ({isci} paralel)...")
    oturum = requests.Session()
    tamam = 0

    with cf.ThreadPoolExecutor(max_workers=isci) as havuz:
        isler = [havuz.submit(okulu_incele, o, oturum) for o in hedefler]
        for is_ in cf.as_completed(isler):
            try:
                is_.result()
            except Exception as hata:
                print(f"  atlandı: {hata}")
            with _kilit:
                tamam += 1
                if tamam % 200 == 0:
                    print(f"  {tamam}/{len(hedefler)}")

    with liste.open("w", encoding="utf-8", newline="") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=list(okullar[0].keys()))
        yazici.writeheader()
        yazici.writerows(okullar)

    ee = sum(1 for o in okullar if o.get("elektrik_elektronik") == "var")
    bt = sum(1 for o in okullar if o.get("bilisim") == "var")
    bilinmez = sum(1 for o in okullar if o.get("elektrik_elektronik") == "bilinmiyor")
    print(f"\nBitti. Elektrik-elektronik: {ee} · Bilişim: {bt} · Tespit edilemeyen: {bilinmez}")
    return tamam


def main() -> None:
    parser = argparse.ArgumentParser(description="Okulların alanlarını (bölümlerini) tespit et")
    parser.add_argument("--liste", type=pathlib.Path, default=pathlib.Path("pazarlama/okullar.csv"))
    parser.add_argument("--il", help="Sadece bu il")
    parser.add_argument("--isci", type=int, default=10)
    args = parser.parse_args()
    calistir(args.liste, args.il, args.isci)


if __name__ == "__main__":
    main()
