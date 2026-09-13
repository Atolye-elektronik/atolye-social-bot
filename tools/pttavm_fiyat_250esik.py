# -*- coding: utf-8 -*-
"""PttAVM fiyatlarini 250 TL kargo esigine gore yeniden kurar.

SORUN: PttAVM'de 250 TL ALTI sepette kargoyu ALICI, ustunde SATICI oder.
Ucuz urunlerin fiyati "alici oder" varsayimiyla kurulmus. Musteri birkac ucuz
urunu tek sepette alip 250'yi gecince kargo bize biniyor ve kar sifirlaniyor
(13.09.2026 ilk siparis: 314,70 TL ciro -> 3,16 TL kar).

COZUM: 250 alti her urune fiyatiyla ORANTILI kargo payi yuklenir:
    yuk = kargo(desi) x fiyat/250
Boylece sepet 250'yi gectiginde yuklerin toplami kargoyu tam karsilar; 250'yi
gecmeyen sepette zaten alici oduyor, yuk bize kar olarak kaliyor. Hicbir
sepetin zarar etmedigi tek kurgu bu.
"""
import json, math, os

S = "C:/Users/serdar/AppData/Local/Temp/claude/C--Users-serdar-Desktop-atolyesocialbotmasaustu/a4d0556e-5012-4f53-831e-17e87b486275/scratchpad/buybox"
D = os.path.dirname(os.path.abspath(__file__))
ESIK = 250.0
# PttAVM desi tarifesi, KDV DAHIL (13.09 kullanici dogrulamasi: sepet desisi
# olculen koli desisi, bildirilen desilerin toplami DEGIL)
TARIFE = {0: 77.50, 1: 78.75, 2: 81.25, 3: 82.50, 4: 85.00, 5: 86.25,
          6: 90.00, 7: 103.75, 8: 125.00, 9: 131.00, 10: 138.75}
KOM = 0.15   # tam_liste'de kullanilan kategori orani (panel %3 gosteriyor ama dogrulanmadi)


def kargo(desi):
    d = int(math.ceil(desi or 1))
    return TARIFE.get(d, TARIFE[10] + (d - 10) * 8.0) / 1.2


def net(p, desi, kom, maliyet):
    k = kargo(desi) * (1.0 if p >= ESIK else p / ESIK)
    return p / 1.2 - p * kom - k - maliyet


def coz(hedef_kar, desi, kom, maliyet):
    """hedef kari veren en dusuk fiyat; 250 esiginde sicrama oldugu icin iki bant ayri denenir."""
    aday = []
    # bant 1: p < 250 -> orantili yuk
    pay = 1 / 1.2 - kom - kargo(desi) / ESIK
    if pay > 0:
        p = (maliyet + hedef_kar) / pay
        if p < ESIK:
            aday.append(p)
    # bant 2: p >= 250 -> tam kargo
    pay2 = 1 / 1.2 - kom
    if pay2 > 0:
        p = (maliyet + hedef_kar + kargo(desi)) / pay2
        if p >= ESIK:
            aday.append(p)
    if not aday:
        return None
    return math.ceil(min(aday) * 100) / 100


def main():
    tam = {x["sk"]: x for x in json.load(open(S + "/tam_liste.json", encoding="utf-8"))}
    panel = {x[0]: {"fiyat": float(x[2]), "desi": float(x[3])}
             for x in json.load(open(D + "/ptt_panel.json", encoding="utf-8"))}
    satir, atla = [], []
    for sk, p in sorted(panel.items()):
        t = tam.get(sk)
        if not t or t.get("maliyet") is None:
            atla.append((sk, "maliyet yok")); continue
        m = float(t["maliyet"])
        eski = p["fiyat"]
        desi = p["desi"] or t.get("desi") or 1
        hedef = (t["kanal"].get("ptt") or {}).get("kar")
        if hedef is None:
            atla.append((sk, "ptt kar hedefi yok")); continue
        yeni = coz(hedef, desi, KOM, m)
        if yeni is None:
            atla.append((sk, "cozulemedi")); continue
        satir.append({"sk": sk, "ad": t["ad"], "desi": desi, "maliyet": m, "hedef_kar": hedef,
                      "eski": eski, "yeni": yeni, "artis": round((yeni / eski - 1) * 100, 1),
                      "eski_kar_sepette": round(net(eski, desi, KOM, m), 2),
                      "yeni_kar_sepette": round(net(yeni, desi, KOM, m), 2)})
    json.dump({"satir": satir, "atlanan": atla}, open(D + "/ptt_fiyat.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    zarar = [s for s in satir if s["eski_kar_sepette"] < 0]
    print("urun %d | atlanan %d" % (len(satir), len(atla)))
    print("250+ sepette ZARAR eden mevcut fiyat: %d urun" % len(zarar))
    print("ortalama artis %%%.1f | degismeyen %d" % (
        sum(s["artis"] for s in satir) / max(len(satir), 1),
        sum(1 for s in satir if abs(s["artis"]) < 0.5)))
    print()
    print("%-16s %-34s %8s %8s %7s %8s" % ("KOD", "AD", "ESKI", "YENI", "ARTIS", "SEPETKAR"))
    for s in sorted(satir, key=lambda x: -x["artis"])[:25]:
        print("%-16s %-34s %8.2f %8.2f %6.1f%% %8.2f" % (
            s["sk"], s["ad"][:34], s["eski"], s["yeni"], s["artis"], s["eski_kar_sepette"]))
    if atla:
        print("\natlananlar:", ", ".join("%s(%s)" % (a, b) for a, b in atla[:15]))


if __name__ == "__main__":
    main()
