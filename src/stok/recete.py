# -*- coding: utf-8 -*-
"""Recete (BOM) motoru.

Stok yalnizca PARCA'larda tutulur. Set stogu hesaplanir:
    set_stok = min( parca_stok // adet )   (ic ice setler ozyinelemeli)
Satis dusumu: set satilinca recetedeki parcalardan duser; tekli parca satilinca
sadece o parcadan duser. Her iki durumda da etkilenen setlerin stogu yeniden hesaplanir.

Girdi: content/recete.json ('coklu_paket', 'setler', 'yeni_parcalar'),
       content/shopify_sku.json ('alias': pazaryeri kodu -> Shopify SKU).
"""
import json
import os
from functools import lru_cache

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Recete:
    def __init__(self, recete_yolu=None, sku_yolu=None):
        r = json.load(open(recete_yolu or os.path.join(KOK, "content", "recete.json"), encoding="utf-8"))
        s = json.load(open(sku_yolu or os.path.join(KOK, "content", "shopify_sku.json"), encoding="utf-8"))
        self.alias = {k: v for k, v in s.get("alias", {}).items() if v}
        self.setler = {k: [tuple(x[:2]) for x in v] for k, v in r["setler"].items()}
        for k, v in r["coklu_paket"].items():
            p = v["parca"]
            self.setler[k] = [(x, v["adet"]) for x in (p if isinstance(p, list) else [p])]
        self.yeni_parcalar = set(r.get("yeni_parcalar", {}))
        self.shopify_sku = set(s.get("sku", {}))
        # set adlarini da kanonik yap; alias ile ayni parcaya cikan 1'lik paketler
        # (AEUNOR32 -> AEUNOR3 gibi) set degil, es-kod: onlari at ki kendine referans olmasin
        temiz = {}
        for k, v in self.setler.items():
            kk = self.kanonik(k)
            kal = [(self.kanonik(p), n) for p, n in v]
            if len(kal) == 1 and kal[0][0] == kk and kal[0][1] == 1:
                continue
            temiz[kk] = kal
        self.setler = temiz

    def kanonik(self, kod):
        """Pazaryeri stok kodunu Shopify SKU'suna cevirir (alias yoksa aynen)."""
        return self.alias.get(kod, kod)

    def set_mi(self, kod):
        return self.kanonik(kod) in self.setler

    def parcalar(self, kod, adet=1):
        """Bir kodun en alt parca ihtiyacini dondurur: {parca: toplam_adet}."""
        kod = self.kanonik(kod)
        if kod not in self.setler:
            return {kod: adet}
        out = {}
        for p, n in self.setler[kod]:
            for pp, nn in self.parcalar(p, n * adet).items():
                out[pp] = out.get(pp, 0) + nn
        return out

    def etkilenen_setler(self, parca):
        """Bu parcayi (dogrudan ya da ic ice) iceren tum setler."""
        parca = self.kanonik(parca)
        return sorted(s for s in self.setler if parca in self.parcalar(s))

    def set_stogu(self, kod, parca_stok):
        """parca_stok: {parca_kodu: adet}. Bilinmeyen parca -> None (hesaplanamaz)."""
        kod = self.kanonik(kod)
        if kod not in self.setler:
            return parca_stok.get(kod)
        vals = []
        for p, n in self.setler[kod]:
            st = self.set_stogu(p, parca_stok)
            if st is None:
                return None
            vals.append(st // n)
        return min(vals) if vals else 0

    def tum_set_stoklari(self, parca_stok):
        return {s: self.set_stogu(s, parca_stok) for s in self.setler}

    def satis_dus(self, kod, adet, parca_stok):
        """Satisi parca stogundan duser; guncellenen parcalari ve etkilenen setleri dondurur."""
        ihtiyac = self.parcalar(kod, adet)
        for p, n in ihtiyac.items():
            parca_stok[p] = max(0, parca_stok.get(p, 0) - n)
        etk = set()
        for p in ihtiyac:
            etk.update(self.etkilenen_setler(p))
        return ihtiyac, sorted(etk)


if __name__ == "__main__":
    import sys
    r = Recete()
    kod = sys.argv[1] if len(sys.argv) > 1 else "AE3IN1ROBOT"
    print(kod, "->", r.parcalar(kod))
    print("etkilenen setler (AEUNOR3):", r.etkilenen_setler("AEUNOR3"))
