# -*- coding: utf-8 -*-
"""state/stok_kaynak.json -> state/stok_hedef.json (kanallara basilacak nihai stok).

TAVAN: pazaryerinde 500'den fazla stok gostermenin faydasi yok, riski var.
ESIK : 2 ve altinda kalan kalem 0 basilir (son parcayi satip gecikmemek icin).
"""
import json, os, re, sys

KOK = "C:/Users/serdar/Desktop/atolye-temiz"
sys.path.insert(0, KOK + "/src")
for l in open(KOK + "/.env", encoding="utf-8"):
    m = re.match(r"([A-Z0-9_]+)=(.*)", l.strip())
    if m:
        os.environ.setdefault(m.group(1), m.group(2).strip().strip('"').strip("'"))
from stok.recete import Recete  # noqa: E402
from stok import shopify_admin as sa  # noqa: E402

# TAVAN burada UYGULANMAZ. Shopify stok masteri; gercek sayiyi tutmali ki set
# hesabi dogru olsun. Tavan yalniz kanallara basarken merkez.py'de uygulanir.
ESIK = 2


def main():
    r = Recete()
    K = json.load(open(KOK + "/state/stok_kaynak.json", encoding="utf-8"))
    mevcut = sa.stoklari_oku()
    ham = dict(K["parca"])
    for s, v in K["set"].items():
        if v is not None:
            ham[s] = v
    # yalniz gercekten urunu olan SKU'lar basilir (Shopify haritasinda olanlar)
    hedef, urunsuz = {}, []
    for k, v in ham.items():
        if k not in mevcut:
            urunsuz.append(k); continue
        v = int(v)
        hedef[k] = 0 if v <= ESIK else v
    json.dump(hedef, open(KOK + "/state/stok_hedef.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, sort_keys=True)
    art = [(k, mevcut[k], v) for k, v in hedef.items() if v > mevcut[k]]
    azal = [(k, mevcut[k], v) for k, v in hedef.items() if v < mevcut[k]]
    ayni = [k for k, v in hedef.items() if v == mevcut[k]]
    sifir = [(k, mevcut[k]) for k, v in hedef.items() if v == 0]
    print("basilacak SKU: %d | artan %d | azalan %d | ayni %d" % (len(hedef), len(art), len(azal), len(ayni)))
    print("urunu olmayan ic parca kodu (basilmayacak, %d): %s" % (len(urunsuz), ", ".join(sorted(urunsuz))))
    print("\nSIFIRA DUSENLER (%d) - bunlar satistan cikar:" % len(sifir))
    for k, m in sorted(sifir):
        print("   %-18s shopify %s -> 0" % (k, m))
    print("\nTAVANA DAYANANLAR (500):", ", ".join(sorted(k for k, v in hedef.items() if v == TAVAN)))
    print("\nEN COK AZALANLAR:")
    for k, m, v in sorted(azal, key=lambda x: x[1] - x[2], reverse=True)[:14]:
        print("   %-18s %-5s -> %-5s" % (k, m, v))
    print("\nEN COK ARTANLAR:")
    for k, m, v in sorted(art, key=lambda x: x[2] - x[1], reverse=True)[:14]:
        print("   %-18s %-5s -> %-5s" % (k, m, v))


if __name__ == "__main__":
    main()
