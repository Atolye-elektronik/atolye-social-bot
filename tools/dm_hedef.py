"""Instagram DM hedef listesini önceliğe göre sıralı üretir.

`okul_iletisim` okulların Instagram hesaplarını topluyor, `okul_bolum` da
hangi bölümlerin olduğunu. Bu betik ikisini birleştirip DM sırasını çıkarıyor:
hesabı olan her okul, bölüm teyidine göre segmentleniyor.

Sıra, `pazarlama/instagram-dm-metinleri.md` içindeki oyun kitabıyla aynı:
elektrik-elektronik teyitli okullar önce, çünkü mesajdaki "alan şefinize
iletin" cümlesi ancak o alan gerçekten varsa karşılık buluyor.

Kullanımı:
    python tools/dm_hedef.py
    python tools/dm_hedef.py --liste pazarlama/okullar.csv
"""

from __future__ import annotations

import argparse
import collections
import csv
import pathlib

KOK = pathlib.Path(__file__).resolve().parent.parent

# DM metinleri dosyasındaki bölüm numaralarıyla eşleşiyor.
SEGMENTLER = {
    "ee": "2-okul-elektrik-elektronik",
    "bt": "2-okul-bilisim",
    "diger": "2-okul-bolum-bilinmiyor",
}


def segment(okul: dict) -> str:
    if okul.get("elektrik_elektronik") == "var":
        return "ee"
    if okul.get("bilisim") == "var":
        return "bt"
    return "diger"


def main() -> None:
    ayristirici = argparse.ArgumentParser(description="Instagram DM hedef listesi üret")
    ayristirici.add_argument("--liste", type=pathlib.Path, default=KOK / "pazarlama/okullar.csv")
    ayristirici.add_argument("--cikti", type=pathlib.Path, default=KOK / "pazarlama/instagram-hedefler.csv")
    args = ayristirici.parse_args()

    with args.liste.open(encoding="utf-8-sig", newline="") as dosya:
        okullar = list(csv.DictReader(dosya))

    hedefler = [o for o in okullar if (o.get("instagram") or "").strip()]
    for okul in hedefler:
        okul["segment"] = SEGMENTLER[segment(okul)]

    # Sıralama: elektrik-elektronik > bilişim > bilinmiyor; her grupta il adına göre.
    oncelik = {"ee": 0, "bt": 1, "diger": 2}
    hedefler.sort(key=lambda o: (oncelik[segment(o)], o.get("il", ""), o.get("okul", "")))

    sutunlar = ["instagram", "okul", "il", "ilce", "segment", "elektrik_elektronik",
                "bilisim", "bolumler", "telefon", "site"]
    args.cikti.parent.mkdir(parents=True, exist_ok=True)
    with args.cikti.open("w", encoding="utf-8", newline="") as dosya:
        yazici = csv.DictWriter(dosya, fieldnames=sutunlar, extrasaction="ignore")
        yazici.writeheader()
        yazici.writerows(hedefler)

    sayac = collections.Counter(segment(o) for o in hedefler)
    print(f"Instagram hesabı olan okul: {len(hedefler)} / {len(okullar)}")
    print(f"  elektrik-elektronik teyitli : {sayac['ee']}")
    print(f"  bilişim teyitli             : {sayac['bt']}")
    print(f"  bölümü bilinmiyor           : {sayac['diger']}")
    print(f"\nyazıldı: {args.cikti.relative_to(KOK)}")

    # Günde 10-15 sınırı oyun kitabından; kaç günlük iş olduğunu göstermek
    # tempo kararını somutlastiriyor.
    if hedefler:
        print(f"Günde 12 mesajla ~{-(-len(hedefler) // 12)} günlük iş.")


if __name__ == "__main__":
    main()
