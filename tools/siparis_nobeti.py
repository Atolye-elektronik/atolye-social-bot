# -*- coding: utf-8 -*-
"""Siparis hattini her sabah ucdan uca dener — para harcamadan.

Kullanici 28.08: *"uzun zamandır siteden sipariş gelmiyor, her gün sabah bir
test siparişi yapar mısın"*.

**Gercek siparis verilmiyor.** Odeme bilgisi girmek bana kapali; ayrica her gun
gercekten odenen bir siparis hem para hem komisyon yakar ve verdigi bilgi
bundan fazla degil. Bunun yerine musterinin yurudugu yol **odeme adimina
kadar** birebir yuruniyor:

    ana sayfa -> urun sayfasi -> sepete ekle -> sepet -> odeme sayfasi

Odeme sayfasi acilip odeme secenekleri (PayTR / havale) gorunuyorsa hat
saglamdir. Gercekte bozulan seyler zaten bu adimlarda bozulur: site duser,
urun yayindan kalkar, magaza sifre korumasina gecer, sepet ucu kirilir, odeme
saglayicisi baglantisi kopar. Kart ekranindan sonrasi PayTR'nin isi.

    python tools/siparis_nobeti.py

Cikis kodu 0 = hat saglam, 1 = bir adim kirik.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

import requests

KOK = pathlib.Path(__file__).resolve().parents[1]
DURUM = KOK / "state" / "siparis_nobeti.json"

SITE = "https://atolyeelektronik.com"

# Tekli staj defteri. Bilerek en ucuz ve her zaman stokta olan urun secildi;
# sinif paketlerinde stok takibi kapali oldugu icin onlar hatayi yakalamaz.
VARYANT = 49882313720037
BEKLENEN_FIYAT = 90.00
URUN_YOLU = "/products/meslek-lisesi-ve-mesem-ogrencileri-icin-isletmelerde-mesleki-egitim-is-dosyasi"

# Odeme sayfasinda bunlardan en az biri gorunmeli
ODEME_IZLERI = ("paytr", "havale", "eft", "kredi kart", "credit card")


def _oturum() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    return s


def dene() -> tuple[bool, list[str]]:
    s = _oturum()
    sorunlar: list[str] = []

    def al(ad: str, yol: str):
        try:
            r = s.get(SITE + yol, timeout=30, allow_redirects=True)
        except Exception as e:
            sorunlar.append(f"{ad}: baglanti hatasi ({str(e)[:60]})")
            return None
        if r.status_code >= 400:
            sorunlar.append(f"{ad}: HTTP {r.status_code}")
        # Magaza sifre korumasina alinirsa hicbir siparis gelmez ve bu
        # disaridan fark edilmez — en sinsi ariza bu.
        elif "/password" in r.url:
            sorunlar.append(f"{ad}: magaza SIFRE KORUMASINDA")
        return r

    al("ana sayfa", "/")
    al("urun sayfasi", URUN_YOLU)

    try:
        r = s.post(SITE + "/cart/add.js", json={"items": [{"id": VARYANT, "quantity": 1}]},
                   timeout=30)
        if r.status_code != 200:
            sorunlar.append(f"sepete ekleme: HTTP {r.status_code}")
        else:
            kalem = r.json().get("items", [r.json()])[0]
            fiyat = kalem.get("price", 0) / 100
            if abs(fiyat - BEKLENEN_FIYAT) > 0.01:
                # Reklamlarda yazan fiyat degistiyse haber ver: reklam ile
                # magaza arasindaki fark en pahali sessiz hata.
                sorunlar.append(f"fiyat degismis: {fiyat:.2f} TL "
                                f"(beklenen {BEKLENEN_FIYAT:.2f})")
    except Exception as e:
        sorunlar.append(f"sepete ekleme: hata ({str(e)[:60]})")

    al("sepet", "/cart")

    try:
        r = s.post(SITE + "/cart", data={"checkout": ""}, timeout=45, allow_redirects=True)
        if r.status_code >= 400:
            sorunlar.append(f"odeme sayfasi: HTTP {r.status_code}")
        elif "/checkouts/" not in r.url:
            sorunlar.append(f"odeme sayfasi acilmadi -> {r.url[:70]}")
        else:
            g = r.text.lower()
            if not any(iz in g for iz in ODEME_IZLERI):
                sorunlar.append("odeme sayfasinda odeme secenegi gorunmuyor")
    except Exception as e:
        sorunlar.append(f"odeme sayfasi: hata ({str(e)[:60]})")

    return (not sorunlar), sorunlar


def main() -> int:
    simdi = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    saglam, sorunlar = dene()

    DURUM.parent.mkdir(parents=True, exist_ok=True)
    gecmis = []
    if DURUM.exists():
        try:
            gecmis = json.loads(DURUM.read_text(encoding="utf-8")).get("gecmis", [])
        except Exception:
            gecmis = []
    gecmis.append({"an": simdi, "saglam": saglam, "sorunlar": sorunlar})
    DURUM.write_text(json.dumps({"gecmis": gecmis[-60:]}, ensure_ascii=False, indent=2),
                     encoding="utf-8")

    if saglam:
        print(f"{simdi}  HAT SAGLAM — urun, sepet ve odeme sayfasi calisiyor")
        return 0
    print(f"{simdi}  SIPARIS HATTI KIRIK:")
    for x in sorunlar:
        print(f"   - {x}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
