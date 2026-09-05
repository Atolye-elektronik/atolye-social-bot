# -*- coding: utf-8 -*-
"""Stok merkezi.

Tek gercek stok: Shopify envanteri (parca bazinda). Bu modul:
  1) Shopify'dan parca stoklarini okur (shopify_admin.py),
  2) Receteyle set stoklarini hesaplar (recete.py),
  3) Her kanala (TY, HB, N11, Pazarama, Idefix, PttAVM) parca+set stoklarini basar,
  4) Kanal siparislerinden gelen satislari Shopify'dan duser (siparis.py cagirir).

Kuru calistirma:  python -m stok.merkez --kuru      (hicbir yere yazmaz, rapor basar)
Dagit:            python -m stok.merkez --dagit     (kanallara stok basar)
"""
import json
import os
import sys
import time

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "src"))

from stok.recete import Recete  # noqa: E402

KRITIK_ESIK = int(os.environ.get("STOK_KRITIK_ESIK", "2"))   # bu ve alti -> diger kanallarda 0
DURUM = os.path.join(KOK, "state", "stok_dagitim.json")


def parca_stoklari():
    """Shopify'dan parca stoklarini ceker. Admin token yoksa son kaydedilen haritayi kullanir."""
    try:
        from stok import shopify_admin
        return shopify_admin.stoklari_oku()
    except Exception as e:  # token yok / ag yok -> son bilinen
        S = json.load(open(os.path.join(KOK, "content", "shopify_sku.json"), encoding="utf-8"))
        print("! Shopify canli okunamadi (%s), shopify_sku.json kullaniliyor" % e)
        return {k: v["qty"] for k, v in S["sku"].items()}


def hedef_stoklar(recete, parca):
    """Kanallara basilacak stok: parcalar + hesaplanan setler; kritik esik altinda 0."""
    hedef = {}
    for k, v in parca.items():
        hedef[k] = v
    for s in recete.setler:
        st = recete.set_stogu(s, parca)
        if st is not None:
            hedef[s] = st
    for k, v in list(hedef.items()):
        if v is not None and v <= KRITIK_ESIK:
            hedef[k] = 0
    return hedef


def kanal_kodu(kanal, shopify_kodu, recete):
    """Shopify SKU -> kanaldaki stok kodu (alias'in tersi). Coklu alias'ta ilkini dondurur."""
    ters = {}
    for a, b in recete.alias.items():
        ters.setdefault(b, []).append(a)
    return ters.get(shopify_kodu, [shopify_kodu])


def dagit(hedef, kanallar, kuru=True):
    from stok import kanallar as K
    sonuc = {}
    for ad in kanallar:
        fn = getattr(K, "stok_bas_" + ad, None)
        if not fn:
            sonuc[ad] = "adaptor yok"; continue
        try:
            sonuc[ad] = fn(hedef, kuru=kuru)
        except Exception as e:
            sonuc[ad] = "HATA %s" % e
    return sonuc


def main():
    kuru = "--dagit" not in sys.argv
    recete = Recete()
    parca = parca_stoklari()
    hedef = hedef_stoklar(recete, parca)
    setler = {s: hedef.get(s) for s in recete.setler}
    print("parca: %d | set: %d | kritik esik: %d" % (len(parca), len(setler), KRITIK_ESIK))
    bilinmeyen = [s for s, v in setler.items() if v is None]
    if bilinmeyen:
        print("hesaplanamayan setler (eksik parca stogu):", ", ".join(bilinmeyen))
    if "--liste" in sys.argv or kuru:
        for s in sorted(recete.setler):
            print("  %-18s %s" % (s, setler[s]))
    kanallar = [a for a in ("trendyol", "hepsiburada", "n11", "pazarama", "idefix", "pttavm")
                if "--kanal" not in sys.argv or a in sys.argv]
    if "--dagit" in sys.argv or "--kuru" in sys.argv:
        sonuc = dagit(hedef, kanallar, kuru=kuru)
        for k, v in sonuc.items():
            print("%-12s %s" % (k, v))
        if not kuru:
            os.makedirs(os.path.dirname(DURUM), exist_ok=True)
            json.dump({"zaman": time.strftime("%Y-%m-%d %H:%M"), "hedef": hedef, "sonuc": {k: str(v)[:300] for k, v in sonuc.items()}},
                      open(DURUM, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
