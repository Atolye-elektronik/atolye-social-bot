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
    # Robotik/kodlama kursları "Özel Çeşitli Kurslar" altında kayıtlı ve
    # tür sütunundan ayırt edilemiyor; kurum adından süzüyoruz.
    "robotik": ("kurs", r"robot|kodlama|yaz[ıi]l[ıi]m|bili[şs]im|maker|teknoloji|bilim akademi"),
    "kurs": ("kurs", r"."),
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


def _duz(parca: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", parca)).strip()


# Python'da "İ".lower() birleşik noktalı bir 'i' üretiyor ve düz "i" ile
# eşleşmiyor; başlıkları karşılaştırmadan önce sadeleştiriyoruz.
_SADE = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iissgguuoocc")


def _anahtarla(metin: str) -> str:
    return re.sub(r"\s+", " ", metin.translate(_SADE)).lower().strip()


def _sutun_haritasi(html: str) -> dict[str, int]:
    """Tablo başlıklarından sütun sırasını çıkarır.

    Dizin, kurum türüne göre farklı tablolar döndürüyor: okul listesinde
    "Kurum Türü" sütunu varken mesem listesinde yok. Sabit sıra varsaymak
    yerine başlığı okuyoruz.
    """
    basliklar = [_anahtarla(_duz(b)) for b in re.findall(r"<th[^>]*>(.*?)</th>", html, re.S | re.I)]
    harita = {}
    for sira, baslik in enumerate(basliklar):
        for anahtar, kelime in (
            ("ilce", "ilce"), ("kurum", "kurum adi"), ("tur", "kurum turu"),
            ("adres", "adres"), ("telefon", "telefon"),
        ):
            if kelime in baslik and anahtar not in harita:
                harita[anahtar] = sira
    return harita


def il_kurumlari(oturum: requests.Session, il: str, ust_tur: str, desen: str) -> list[dict]:
    yanit = oturum.get(
        DIZIN, params={"tur": ust_tur, "il": il, "tur2": "0"}, timeout=60,
        headers={"User-Agent": "atolye-social-bot"},
    )
    yanit.raise_for_status()

    harita = _sutun_haritasi(yanit.text)
    if "kurum" not in harita:
        return []

    def al(hucre: list[str], anahtar: str) -> str:
        yer = harita.get(anahtar)
        return hucre[yer].strip() if yer is not None and yer < len(hucre) else ""

    kurumlar = []
    for satir in re.findall(r"<tr[^>]*>(.*?)</tr>", yanit.text, re.S | re.I):
        hucre = [_duz(h) for h in re.findall(r"<td[^>]*>(.*?)</td>", satir, re.S | re.I)]
        if len(hucre) <= harita["kurum"]:
            continue

        ad = al(hucre, "kurum")
        tur = al(hucre, "tur")
        if not ad:
            continue
        # Tür sütunu yoksa (mesem listesi) filtreyi kurum adına uyguluyoruz.
        # Tür sütunu ayırt edici değilse (kurslar) kurum adına bakıyoruz.
        hedef = ad if desen != r"mesleki ve teknik anadolu lisesi" else (tur or ad)
        if not re.search(desen, hedef, re.I):
            continue

        kurumlar.append({
            "il": il,
            "ilce": al(hucre, "ilce"),
            "kurum": ad,
            "tur": tur or ust_tur,
            "adres": al(hucre, "adres"),
            "telefon": al(hucre, "telefon"),
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

    # Dizin bazı türlerde il filtresini uygulamıyor ve aynı kaydı her il için
    # döndürüyor; bu yüzden kurum adına göre tekilleştiriyoruz.
    tekil = list({k["kurum"]: k for k in kurumlar}.values())
    tekil.sort(key=lambda k: (k["il"], k["ilce"], k["kurum"]))

    args.cikti.parent.mkdir(parents=True, exist_ok=True)
    with args.cikti.open("w", encoding="utf-8", newline="") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=["il", "ilce", "kurum", "tur", "adres", "telefon"])
        yazici.writeheader()
        yazici.writerows(tekil)

    print(f"\nToplam {len(tekil)} kurum yazıldı: {args.cikti}")


if __name__ == "__main__":
    main()
