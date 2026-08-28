# -*- coding: utf-8 -*-
"""Organik paylaşım kuyruğunu reklam vitriniyle hizalar.

Sorun (28.08'de bulundu): 1-14 Eylül'de reklamda **defterler** öne çıkacak ama
o iki haftadaki organik içeriğin 8 tanesi robot kiti, yalnız 2 tanesi defter.
Reklama para verip defter gösterirken profilde robot kiti anlatmak, iki kanalın
birbirini beslemesini engelliyor. Üstelik robot kitlerine reklamda bilerek
ufak pay verildi — organikte ise başroldeydi.

Yöntem: vitrin penceresindeki YANLIŞ aileden postla, pencere DIŞINDAKİ doğru
aileden postun tarihlerini takas eder. Post silinmez, üretilmez; yalnız sıra
değişir. Böylece toplam içerik akışı ve çeşitliliği korunur.

Güvenlik: `state/published.json` içinde kaydı olan post (kısmen bile
yayınlanmış olsa) **taşınmaz** — tarihi/dosya adı değişirse mükerrer paylaşım
riski doğar.

    python tools/kuyruk_duzenle.py            # kuru çalışma
    python tools/kuyruk_duzenle.py --uygula
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.posts import load_post  # noqa: E402

KOK = pathlib.Path(__file__).resolve().parents[1]
POSTLAR = KOK / "posts"
KAYIT = KOK / "state" / "published.json"
TZ = dt.timezone(dt.timedelta(hours=3))

AILE_DESEN = [
    ("defter", r"defter|is-dosyasi|staj|temrin"),
    ("takim", r"takim-cantasi|el-alet|pense|tornavida|havya|multimetre|lehim"),
    ("endustriyel", r"endustriyel"),
    ("arduino", r"arduino.*(set|baslangic|egitim)|proje-ve-uygulama"),
    ("robot", r"robot"),
]

# Reklam vitrini (google-ads-kurulum.md bolum 6 ile ayni)
PENCERELER = [
    (dt.datetime(2026, 9, 1, tzinfo=TZ), dt.datetime(2026, 9, 15, tzinfo=TZ), "defter"),
    (dt.datetime(2026, 9, 15, tzinfo=TZ), dt.datetime(2026, 9, 22, tzinfo=TZ), "takim"),
]


def aile(slug: str) -> str:
    for ad, desen in AILE_DESEN:
        if re.search(desen, slug, re.I):
            return ad
    return "diger"


def yayinlanmislar() -> set:
    if not KAYIT.exists():
        return set()
    ham = json.loads(KAYIT.read_text(encoding="utf-8"))
    kayitlar = ham.get("posts", ham)
    return {k for k, v in kayitlar.items() if v}


def kuyruk():
    simdi = dt.datetime.now(TZ)
    basildi = yayinlanmislar()
    cikti = []
    for f in sorted(POSTLAR.glob("*.md")):
        try:
            p = load_post(f)
        except Exception:
            continue
        if not p.publish_at or p.publish_at <= simdi:
            continue
        cikti.append({
            "yol": f, "slug": p.slug, "an": p.publish_at,
            "aile": aile(p.slug), "kilitli": p.slug in basildi,
        })
    cikti.sort(key=lambda x: x["an"])
    return cikti


def takaslari_bul(kayitlar):
    """Pencere içindeki yanlış aile ile pencere dışındaki doğru aileyi eşler."""
    takaslar = []
    kullanilan = set()
    for bas, son, hedef in PENCERELER:
        # Yalnizca robot ve dolgu icerik yerinden edilir. Defter, takim,
        # arduino, endustriyel sezonluk deger tasiyor; bunlari pencereden
        # cikarip Kasim'a surmek kazanctan cok kayip olur.
        TASINABILIR = {"robot", "diger"}
        icerde = [k for k in kayitlar
                  if bas <= k["an"] < son and k["aile"] != hedef
                  and k["aile"] in TASINABILIR and not k["kilitli"]]
        # Adaylar yalnizca pencereden SONRA olanlar. Pencere oncesindekini
        # cekmek zarar verir: ornegin 29.08'deki defter postu zaten vitrinin
        # hemen oncesinde iyi bir yerde; onu ileri itip yerine robot koymak
        # ters teper.
        adaylar = [k for k in kayitlar
                   if k["an"] >= son and k["aile"] == hedef
                   and not k["kilitli"] and id(k) not in kullanilan]
        # Pencere icinde once "en alakasiz" olani degistir: robot > diger
        oncelik = {"robot": 0, "diger": 1}
        icerde.sort(key=lambda k: (oncelik.get(k["aile"], 2), k["an"]))
        for disari in adaylar:
            if not icerde:
                break
            iceri = icerde.pop(0)
            takaslar.append((iceri, disari))
            kullanilan.add(id(disari))
            kullanilan.add(id(iceri))
    return takaslar


def _tarih_degistir(yol: pathlib.Path, yeni_an: dt.datetime) -> pathlib.Path:
    """publish_at satırını günceller ve dosya adındaki tarih önekini eşitler."""
    metin = yol.read_text(encoding="utf-8")
    yeni_metin, adet = re.subn(
        r"^publish_at:.*$",
        f"publish_at: {yeni_an:%Y-%m-%d %H:%M}",
        metin, count=1, flags=re.MULTILINE,
    )
    if adet != 1:
        raise RuntimeError(f"publish_at satiri bulunamadi: {yol.name}")
    yol.write_text(yeni_metin, encoding="utf-8")

    yeni_ad = re.sub(r"^\d{4}-\d{2}-\d{2}", f"{yeni_an:%Y-%m-%d}", yol.name)
    if yeni_ad != yol.name:
        hedef = yol.with_name(yeni_ad)
        yol.rename(hedef)
        return hedef
    return yol


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uygula", action="store_true")
    a = ap.parse_args()

    kayitlar = kuyruk()
    takaslar = takaslari_bul(kayitlar)

    if not takaslar:
        print("Takas gerekmiyor.")
        return 0

    print(f"{len(takaslar)} takas onerisi:\n")
    for iceri, disari in takaslar:
        print(f"  {iceri['an']:%d.%m %H:%M} {iceri['aile']:11s} {iceri['slug'][:44]}")
        print(f"  {disari['an']:%d.%m %H:%M} {disari['aile']:11s} {disari['slug'][:44]}")
        print(f"     -> tarihler takas edilecek\n")

    kilitli = [k for k in kayitlar if k["kilitli"]]
    if kilitli:
        print(f"({len(kilitli)} post kismen yayinlandigi icin dokunulmuyor)")

    if not a.uygula:
        print("\n--- KURU CALISMA --- uygulamak icin: --uygula")
        return 0

    print()
    for iceri, disari in takaslar:
        i_an, d_an = iceri["an"], disari["an"]
        _tarih_degistir(iceri["yol"], d_an)
        _tarih_degistir(disari["yol"], i_an)
        print(f"  takas: {iceri['slug'][:40]} -> {d_an:%d.%m} | "
              f"{disari['slug'][:40]} -> {i_an:%d.%m}")
    print(f"\n{len(takaslar)} takas uygulandi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
