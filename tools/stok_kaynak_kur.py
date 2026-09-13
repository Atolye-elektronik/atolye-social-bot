# -*- coding: utf-8 -*-
"""Fatura-eksi-satis stogunu (stok_hesap.json) Shopify SKU duzlemine tasir.

Cikti: state/stok_kaynak.json  {"parca": {sku: adet}, "bilinmeyen": [...], "tarih": ...}
Bu dosya bundan sonra stok merkezinin GERCEK kaynagi. Shopify envanteri buradan yazilir.
"""
import datetime, json, os, sys

KOK = "C:/Users/serdar/Desktop/atolye-temiz"
SB = "C:/Users/serdar/AppData/Local/Temp/claude/C--Users-serdar-Desktop-atolyesocialbotmasaustu/a4d0556e-5012-4f53-831e-17e87b486275/scratchpad/buybox"
sys.path.insert(0, KOK + "/src")
from stok.recete import Recete  # noqa: E402

# AILE: degeri/rengi farkli ama BIZIM ICIN AYNI malzeme olan kodlar tek havuzda
# toplanir (kullanici karari 13.09.2026). Faturalar deger kirilimi vermiyor;
# 330 ohm ile 10k direnci ayri ayri saymanin anlami yok. Havuzdaki her uye ayni
# stok sayisini gosterir ve hangisi satilirsa havuzdan duser.
#   kanonik (Shopify'da urunu OLAN kod) -> ayni havuza giren diger kodlar
AILE = {
    "AEDIR330":    ["AEDIRENC", "AEDIRENC-END", "AEDIR10K"],   # tum karbon direncler
    "AELED5K":     ["AELED", "AELED5M", "AELED5Y"],            # 5mm LED, tum renkler
    "AEBTN6X6":    ["AEBTN6PIN"],                              # butonlar
    "AEPOT10K":    ["AEMONOPOT"],                              # potansiyometreler
    "AEGUCELEMAN": ["AEBCTRANS"],                              # transistor + guc elemani
    "AEJK2040":    ["AEJK2040DE", "AEJK2040DD", "AEJK2040EE"], # jumper, tum tipler
}
UYE = {u: k for k, v in AILE.items() for u in v}

TUKENDI = {"AEUT12D"}
# Faturasi olmayan/eksik kalemler icin ELLE verilen stok. Hesap bunlari negatif
# gosteriyor ve tek basina 5 seti sifira dusuruyor -> acik varsayimla ezildi.
# Alim defterine giremeyen kalemler icin kacamak. Su an bos: kutunun 200 adedi
# 13.09'da alim defterine "faturasiz (kullanici beyani)" basligiyla islendi.
ELLE_ALIM = {}


def main():
    r = Recete()
    D = {x["kod"]: x for x in json.load(open(SB + "/stok_hesap.json", encoding="utf-8"))}
    parca = {}
    for kod, x in D.items():
        k = x.get("kalan")
        if k is None:
            continue
        sku = r.kanonik(UYE.get(kod, kod))
        parca[sku] = parca.get(sku, 0) + max(0, int(k))   # ayni aileyse havuza eklenir
    for k in TUKENDI:
        parca[r.kanonik(k)] = 0
    for k, v in ELLE_ALIM.items():
        sku = r.kanonik(k)
        d = D.get(k) or {}
        tuketim = int(d.get("satis") or 0)
        parca[sku] = max(0, v - tuketim)
    # havuz uyelerinin hepsi ayni sayiyi gosterir (kanal ve Shopify icin)
    for kanonik, uyeler in AILE.items():
        for u in uyeler:
            parca[u] = parca.get(kanonik, 0)

    # recetelerin ihtiyac duydugu tum yaprak parcalar
    gerekli = set()
    for s in r.setler:
        gerekli.update(r.parcalar(s))
    bilinmeyen = sorted(p for p in gerekli if p not in parca)

    setler = {}
    for s in sorted(r.setler):
        st = r.set_stogu(s, parca)
        setler[s] = st

    out = {"tarih": datetime.date.today().isoformat(), "parca": parca,
           "bilinmeyen": bilinmeyen, "set": setler}
    json.dump(out, open(KOK + "/state/stok_kaynak.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    print("parca stogu: %d kod | recete parcasi: %d | stogu BILINMEYEN: %d"
          % (len(parca), len(gerekli), len(bilinmeyen)))
    if bilinmeyen:
        print("  bilinmeyenler:", ", ".join(bilinmeyen))
    hesaplanamayan = [s for s, v in setler.items() if v is None]
    sifir = [s for s, v in setler.items() if v == 0]
    print("set: %d | hesaplanamayan: %d | sifir cikan: %d" % (len(setler), len(hesaplanamayan), len(sifir)))
    if hesaplanamayan:
        print("  hesaplanamayan:", ", ".join(hesaplanamayan))
    if sifir:
        print("  sifir:", ", ".join(sifir))


if __name__ == "__main__":
    main()
