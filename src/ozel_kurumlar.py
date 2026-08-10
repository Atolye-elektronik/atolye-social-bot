"""MEB Özel Öğretim Kurumları dizininden özel okul ve kursları çıkarır.

MEB'in okul bağlantıları dizini (src/okul_listesi.py) yalnızca devlet
okullarını içeriyor. Özel meslek liseleri, özel mesleki eğitim merkezleri ve
özel kurslar ayrı bir müdürlüğün dizininde: ookgm.meb.gov.tr.

Bu dizin kurum adı, tür, ilçe, adres ve telefon veriyor — e-posta ve web
sitesi vermiyor. Yani devlet okullarındaki gibi kurum kodundan e-posta
türetemiyoruz; bu kurumlara telefon, Instagram ya da web sitelerinden
ulaşmak gerekiyor.

Kullanımı:
    python -m src.ozel_kurumlar --tur mtal --cikti pazarlama/ozel-mtal.csv
    python -m src.ozel_kurumlar --tur mesem --cikti pazarlama/ozel-mesem.csv
    python -m src.ozel_kurumlar --tur kurs --cikti pazarlama/ozel-kurs.csv
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import re
import sys
import time

import requests

DIZIN = "https://ookgm.meb.gov.tr/kurumlar.php"
BEKLEME = 1.0

# Dizindeki üst tür (?tur=) ve kurum türü sütununda aradığımız metin.
TURLER = {
    "mtal": ("okul", r"mesleki ve teknik anadolu lisesi"),
    "mesem": ("mesem", r"mesleki e[ğg]itim merkezi"),
    # Robotik/kodlama kursları bu iki türün altında geçiyor.
    "kurs": ("kurs", r"kurs"),
    "ogretim": ("ozelogretim", r"kurs"),
}

ILLER = [
    "ADANA","ADIYAMAN","AFYONKARAHİSAR","AĞRI","AKSARAY","AMASYA","ANKARA","ANTALYA","ARDAHAN",
    "ARTVİN","AYDIN","BALIKESİR","BARTIN","BATMAN","BAYBURT","BİLECİK","BİNGÖL","BİTLİS","BOLU",
    "BURDUR","BURSA","ÇANAKKALE","ÇANKIRI","ÇORUM","DENİZLİ","DİYARBAKIR","DÜZCE","EDİRNE","ELAZIĞ",
    "ERZİNCAN","ERZURUM","ESKİŞEHİR","GAZİANTEP","GİRESUN","GÜMÜŞHANE","HAKKARİ","HATAY","IĞDIR",
    "ISPARTA","İSTANBUL","İZMİR","KAHRAMANMARAŞ","KARABÜK","KARAMAN","KARS","KASTAMONU","KAYSERİ",
    "KIRIKKALE","KIRKLARELİ","KIRŞEHİR","KİLİS","KOCAELİ","KONYA","KÜTAHYA","MALATYA","MANİSA",
    "MARDİN","MERSİN","MUĞLA","MUŞ","NEVŞEHİR","NİĞDE","ORDU","OSMANİYE","RİZE","SAKARYA","SAMSUN",
    "SİİRT","SİNOP","SİVAS","ŞANLIURFA","ŞIRNAK","TEKİRDAĞ","TOKAT","TRABZON","TUNCELİ","UŞAK",
    "VAN","YALOVA","YOZGAT","ZONGULDAK",
]


def _hucreler(satir: str) -> list[str]:
    ham = re.findall(r"<td[^>]*>(.*?)</td>", satir, re.S | re.I)
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip() for h in ham]


def il_kurumlari(oturum: requests.Session, il: str, ust_tur: str, desen: str) -> list[dict]:
    yanit = oturum.get(
        DIZIN, params={"tur": ust_tur, "il": il, "tur2": "0"}, timeout=60,
        headers={"User-Agent": "atolye-social-bot"},
    )
    yanit.raise_for_status()

    kurumlar = []
    for satir in re.findall(r"<tr[^>]*>(.*?)</tr>", yanit.text, re.S | re.I):
        hucre = _hucreler(satir)
        # Sütunlar: sıra | ilçe | kurum adı | kurum türü | adres | telefon
        if len(hucre) < 6:
            continue
        _, ilce, ad, tur, adres, telefon = hucre[:6]
        if not re.search(desen, tur, re.I):
            continue
        kurumlar.append({
            "il": il,
            "ilce": ilce,
            "kurum": ad.strip(),
            "tur": tur.strip(),
            "adres": adres.strip(),
            "telefon": telefon.strip(),
        })
    return kurumlar


def topla(tur: str, iller: list[str]) -> list[dict]:
    ust_tur, desen = TURLER[tur]
    oturum = requests.Session()

    hepsi: list[dict] = []
    for sira, il in enumerate(iller, start=1):
        try:
            bulunan = il_kurumlari(oturum, il, ust_tur, desen)
        except requests.RequestException as hata:
            print(f"  [{sira}/{len(iller)}] {il} atlandı: {hata}", file=sys.stderr)
            continue
        hepsi += bulunan
        print(f"  [{sira}/{len(iller)}] {il}: {len(bulunan)} kurum")
        if sira < len(iller):
            time.sleep(BEKLEME)
    return hepsi


def main() -> None:
    parser = argparse.ArgumentParser(description="MEB özel öğretim kurumları dizinini tara")
    parser.add_argument("--tur", choices=sorted(TURLER), default="mtal")
    parser.add_argument("--il", help="Virgülle ayrılmış il adları (boşsa 81 il)")
    parser.add_argument("--cikti", type=pathlib.Path, required=True)
    args = parser.parse_args()

    iller = [p.strip().upper() for p in args.il.split(",")] if args.il else ILLER
    print(f"{len(iller)} il taranıyor (özel {args.tur})...")
    kurumlar = topla(args.tur, iller)

    # Aynı kurum aynı ilde iki kez listelenebiliyor.
    tekil = list({(k["il"], k["kurum"]): k for k in kurumlar}.values())
    tekil.sort(key=lambda k: (k["il"], k["ilce"], k["kurum"]))

    args.cikti.parent.mkdir(parents=True, exist_ok=True)
    with args.cikti.open("w", encoding="utf-8", newline="") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=["il", "ilce", "kurum", "tur", "adres", "telefon"])
        yazici.writeheader()
        yazici.writerows(tekil)

    print(f"\nToplam {len(tekil)} kurum yazıldı: {args.cikti}")


if __name__ == "__main__":
    main()
