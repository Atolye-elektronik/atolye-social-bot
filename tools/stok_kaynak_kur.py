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

# stok_hesap'ta GRUP ile birlestirilen kodlar. Fatura satirlari renk/deger ayirmadigi
# icin toplam stok alt kodlara ESIT BOLUNUR (ayni fiziksel yigin, ucu birden sayilmasin).
GRUP_ACK = {
    "AELED":    ["AELED5K", "AELED5M", "AELED5Y"],
    "AEDIRENC": ["AEDIR330", "AEDIR10K"],
    "AEJK2040": ["AEJK2040DE", "AEJK2040DD", "AEJK2040EE"],
}
TUKENDI = {"AEUT12D"}
# Faturasi olmayan/eksik kalemler icin ELLE verilen stok. Hesap bunlari negatif
# gosteriyor ve tek basina 5 seti sifira dusuruyor -> acik varsayimla ezildi.
ELLE = {"AEPLSTKKT": 30}   # renkli malzeme kutusu: alim faturasi YOK, 18 tuketilmis


def main():
    r = Recete()
    D = {x["kod"]: x for x in json.load(open(SB + "/stok_hesap.json", encoding="utf-8"))}
    parca = {}
    for kod, x in D.items():
        k = x.get("kalan")
        if k is None:
            continue
        alts = GRUP_ACK.get(kod, [])
        if alts:
            pay = max(0, int(k)) // len(alts)
            parca[r.kanonik(kod)] = max(0, int(k))      # grup kodunun kendisi (recete icin)
            for alt in alts:
                parca[r.kanonik(alt)] = pay              # alt kodlar: esit bolunmus
        else:
            parca[r.kanonik(kod)] = max(0, int(k))
    for k in TUKENDI:
        parca[r.kanonik(k)] = 0
    for k, v in ELLE.items():
        parca[r.kanonik(k)] = v

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
