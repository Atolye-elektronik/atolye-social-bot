"""Okul listesine telefon, adres ve (varsa) Instagram bilgisini ekler.

`src/okul_listesi.py` her okulun adını, kurumsal e-postasını ve web sitesini
veriyor ama telefonunu vermiyor. Telefon aslında en değerli sütun: okula
ulaşmanın en hızlı yolu WhatsApp, ve MEB sitelerinin hepsinde numara açık
duruyor.

Instagram'ı da deniyoruz ama beklenti düşük tutulmalı: okulların çok azı
sitesinde Instagram bağlantısı veriyor (denemede 16 okulun 1'i). Bulunamayan
hesapları burada tahmin etmiyoruz — yanlış hesaba mesaj atmak, hiç atmamaktan
kötü.

Betik durdurulup yeniden çalıştırılabilir: daha önce doldurulmuş satırlara
tekrar gitmez.

Kullanımı:
    python -m src.okul_iletisim --liste pazarlama/okullar.csv --sadece-genel
    python -m src.okul_iletisim --liste pazarlama/okullar.csv --il ANTALYA
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
SAYFALAR = ("/", "/tema/iletisim.php")
EK_SUTUNLAR = ["telefon", "adres", "instagram"]

# Instagram bağlantılarında kullanıcı adı olmayan yollar
IG_YOK = {"p", "explore", "accounts", "reel", "reels", "stories", "tv", "instagram"}

_kilit = threading.Lock()


def _metin(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def telefon_bul(html: str) -> str:
    metin = _metin(html)
    # "0 242 515 11 08", "(242) 515 1108", "0212 334 58 40" gibi biçimler
    kaliplar = [
        r"0\s?\(?\d{3}\)?\s?\d{3}\s?\d{2}\s?\d{2}",
        r"\(\d{3}\)\s?\d{3}\s?\d{2}\s?\d{2}",
        r"\(\d{3}\)\s?\d{3}\s?\d{4}",
    ]
    for kalip in kaliplar:
        eslesme = re.search(kalip, metin)
        if eslesme:
            rakam = re.sub(r"\D", "", eslesme.group(0))
            if len(rakam) == 10:
                rakam = "0" + rakam
            if len(rakam) == 11 and rakam.startswith("0"):
                return f"{rakam[0:4]} {rakam[4:7]} {rakam[7:9]} {rakam[9:11]}"
    return ""


def adres_bul(html: str) -> str:
    metin = _metin(html)
    eslesme = re.search(r"Adres[:\s]+(.{15,120}?)(?:Telefon|Ulaşım|e-P|Sayfayı|$)", metin, re.I)
    return eslesme.group(1).strip(" .:-") if eslesme else ""


def instagram_bul(html: str) -> str:
    for kullanici in re.findall(r"instagram\.com/([A-Za-z0-9_.]{3,40})", html):
        if kullanici.lower() not in IG_YOK:
            return "@" + kullanici
    return ""


def okulu_zenginlestir(okul: dict, oturum: requests.Session) -> dict:
    birlesik = ""
    for yol in SAYFALAR:
        try:
            yanit = oturum.get(okul["site"] + yol, timeout=20, headers={"User-Agent": UA})
            if yanit.ok:
                birlesik += yanit.text
        except requests.RequestException:
            continue

    if birlesik:
        okul["telefon"] = telefon_bul(birlesik)
        okul["adres"] = adres_bul(birlesik)
        okul["instagram"] = instagram_bul(birlesik)
    return okul


def _yaz(liste: pathlib.Path, okullar: list[dict]) -> None:
    """Listeyi diske yazar. Ara kayıtta da, bitişte de aynı yol kullanılıyor.

    Önce geçici dosyaya yazıp sonra taşıyoruz: koşu tam yazma anında kesilirse
    yarım bir CSV kalmasın, elde ya eski ya yeni tam sürüm olsun.
    """
    gecici = liste.with_suffix(liste.suffix + ".tmp")
    with gecici.open("w", encoding="utf-8", newline="") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=list(okullar[0].keys()))
        yazici.writeheader()
        yazici.writerows(okullar)
    gecici.replace(liste)


def calistir(
    liste: pathlib.Path,
    sadece_genel: bool = False,
    il: str | None = None,
    isci: int = 8,
) -> int:
    with liste.open(encoding="utf-8", newline="") as dosya:
        okullar = list(csv.DictReader(dosya))

    for okul in okullar:
        for sutun in EK_SUTUNLAR:
            okul.setdefault(sutun, "")

    def hedef_mi(okul: dict) -> bool:
        if okul.get("telefon"):  # daha önce dolduruldu
            return False
        if sadece_genel and okul.get("oncelik") != "genel":
            return False
        if il and okul.get("il", "").upper() != il.upper():
            return False
        return bool(okul.get("site"))

    hedefler = [o for o in okullar if hedef_mi(o)]
    if not hedefler:
        print("Zenginleştirilecek yeni okul yok.")
        return 0

    print(f"{len(hedefler)} okulun sitesine bakılıyor ({isci} paralel)...")
    oturum = requests.Session()
    tamam = 0

    with cf.ThreadPoolExecutor(max_workers=isci) as havuz:
        isler = {havuz.submit(okulu_zenginlestir, o, oturum): o for o in hedefler}
        for is_ in cf.as_completed(isler):
            try:
                is_.result()
            except Exception as hata:  # tek okul patlarsa taramayı durdurma
                print(f"  atlandı: {hata}")
            with _kilit:
                tamam += 1
                if tamam % 100 == 0:
                    # Ara kayıt: koşu yarıda kesilirse buraya kadarki veriler
                    # durur ve sonraki çalıştırma kaldığı yerden devam eder.
                    _yaz(liste, okullar)
                    print(f"  {tamam}/{len(hedefler)} (kaydedildi)")

    _yaz(liste, okullar)

    tel = sum(1 for o in okullar if o.get("telefon"))
    ig = sum(1 for o in okullar if o.get("instagram"))
    print(f"\nBitti. Listede telefonu olan: {tel}/{len(okullar)} · Instagram'ı olan: {ig}")
    return tamam


def main() -> None:
    parser = argparse.ArgumentParser(description="Okul listesine telefon ve Instagram ekle")
    parser.add_argument("--liste", type=pathlib.Path, default=pathlib.Path("pazarlama/okullar.csv"))
    parser.add_argument("--sadece-genel", action="store_true", help="Dar alan okullarını atla")
    parser.add_argument("--il", help="Sadece bu il (ör. ANTALYA)")
    parser.add_argument("--isci", type=int, default=8)
    args = parser.parse_args()
    calistir(args.liste, args.sadece_genel, args.il, args.isci)


if __name__ == "__main__":
    main()
