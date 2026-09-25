# -*- coding: utf-8 -*-
"""Telegram bildirimleri: 14:00 TR'de kargoya verilmeyen siparisler, 24:00
TR'de gunun toplam cirosu. Siparis basina anlik bildirimden AYRIDIR.

25.09.2026 YENIDEN YAZILDI (kullanici talebi): eski 09:00/18:00 "hepsi bir
arada" ozeti (satis+kargo+kritik stok) kaldirildi; artik yalnizca bu iki rapor
var, baska bir sey eklenmiyor. Ayrica saat hatasi duzeltildi: GitHub Actions
runner'i UTC calisiyor, datetime.now() kullanilinca mesajdaki saat gercek TR
saatinden 3 saat geri gorunuyordu. Artik stok.bildirim.simdi_tr() (sabit
UTC+3 - Turkiye DST uygulamiyor) kullaniliyor.

    python tools/telegram_ozet.py --kargo    # 14:00 TR: kargoya verilmemis siparisler
    python tools/telegram_ozet.py --ciro     # 24:00 TR: biten gunun toplam cirosu
    python tools/telegram_ozet.py --kargo --kuru   # ekrana basar, Telegram'a GONDERMEZ
"""
import io
import os
import sys
from datetime import timedelta

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [KOK, os.path.join(KOK, "src"), os.path.join(KOK, "src", "marketplaces")]

for _p in (os.path.join(KOK, ".env"),):          # yerelde calistirinca anahtarlari yukle
    if os.path.exists(_p):
        for _l in io.open(_p, encoding="utf-8"):
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from stok import bildirim, siparis  # noqa: E402

# Bu kelimeler durumda geciyorsa is bitmis demektir; gerisi "kargoya verilmedi".
KAPALI = ("ship", "deliver", "teslim", "fulfil", "cancel", "iptal", "iade", "return", "unsupplied", "refund")
ACIK_ZORLA = ("unfulfilled", "unshipped", "unpacked", "partially_fulfilled", "partially fulfilled",
              "shipment_picking", "picking", "hazirlan", "hazırlan")  # Idefix "shipment_picking" icinde "ship" geciyor
DURUM_AD = {"picking": "etiket basildi, kargo almadi", "created": "yeni, hazirlanmadi",
            "invoiced": "faturalandi, kargo almadi", "unfulfilled": "kargolanmadi",
            "partially_fulfilled": "kismen kargolandi", "get_packages": "paketlendi, kargo almadi",
            "get_new_order_items": "yeni, hazirlanmadi", "get_unpacked_packages": "paketlenmedi",
            "open": "yeni, hazirlanmadi", "processing": "hazirlaniyor", "readytoship": "kargoya hazir",
            "shipment_picking": "hazirlaniyor, kargo almadi"}
KANAL_AD = {"shopify": "Site", "trendyol": "Trendyol", "hepsiburada": "Hepsiburada", "n11": "N11",
            "pazarama": "Pazarama", "idefix": "Idefix", "amazon": "Amazon"}


def acik_mi(o):
    d = str(o.get("durum") or "").lower()
    # "unfulfilled" icinde "fulfil" gectigi icin once bunlara bakiyoruz (aksi halde
    # Shopify'in kargolanmamis siparisi "kapali" sayiliyordu).
    if any(a in d for a in ACIK_ZORLA):
        return True
    return not any(k in d for k in KAPALI)


def kalem_metni(o):
    kl = o.get("kalemler") or []
    s = ", ".join("%s x%s" % (k.get("kod") or k.get("barkod") or "?", k.get("adet") or 1) for k in kl)
    return s or str(o.get("durum") or "")


def siparisleri_topla():
    """{kanal: [siparis]} + okunamayan kanallar."""
    out, hata = {}, []
    for k, fn in siparis.TOPLAYICI.items():
        try:
            out[k] = fn() or []
        except Exception as e:
            hata.append("%s: %s" % (KANAL_AD.get(k, k), str(e)[:50]))
    return out, hata


def gunun_satisi(hepsi, gun_str):
    """gun_str: 'YYYY-MM-DD' (TR takvim gunu). Adet, toplam TL, kanal kirilimi (iptaller haric)."""
    adet, tutar, kanal = 0, 0.0, {}
    for k, L in hepsi.items():
        for o in L:
            t = siparis._zaman(o.get("tarih"))
            if not t or t.strftime("%Y-%m-%d") != gun_str:
                continue
            if siparis._iptal_mi(o.get("durum")):
                continue
            adet += 1
            kanal[k] = kanal.get(k, 0) + 1
            try:
                tutar += float(o.get("tutar") or 0)
            except (TypeError, ValueError):
                pass
    return adet, tutar, kanal


def pttavm_acik():
    """PttAVM'nin siparis API'si yok: Gmail'deki siparis mailleri Apps Script ile Sheet'e yazilir,
    ayni web uygulamasi ?tip=pttavm ile 'yeni' olanlari JSON dondurur (docs/pttavm_gmail_appsscript.gs)."""
    url = os.environ.get("STOK_SHEET_WEBHOOK", "").strip()
    if not url:
        return []
    try:
        import requests
        r = requests.get(url, params={"tip": "pttavm"}, timeout=30)
        d = r.json()
        return d if isinstance(d, list) else []
    except Exception:
        return []


def metin_kargo():
    """14:00 TR: su an kargoya verilmemis TUM siparisler (kanal kirilimi + liste)."""
    an = bildirim.simdi_tr()
    hepsi, hata = siparisleri_topla()
    sat = ["🚚 <b>Kargoya verilmemiş siparişler</b> — %s" % an.strftime("%d.%m %H:%M"), ""]

    acik = {k: [o for o in L if acik_mi(o)] for k, L in hepsi.items()}
    toplam = sum(len(v) for v in acik.values())
    sat.append("<b>Toplam: %d sipariş</b>" % toplam)
    for k, liste in acik.items():
        if not liste:
            continue
        sat.append("\n<b>%s (%d)</b>" % (KANAL_AD.get(k, k), len(liste)))
        for o in sorted(liste, key=lambda x: str(x.get("tarih")))[:20]:
            t = siparis._zaman(o.get("tarih"))
            d = str(o.get("durum") or "").lower()
            aciklama = DURUM_AD.get(d, o.get("durum") or "")
            sat.append("• %s %s — %s <i>(%s)</i>" % (t.strftime("%d.%m") if t else "", o.get("no"),
                                                     kalem_metni(o)[:70], aciklama))
        if len(liste) > 20:
            sat.append("• ... +%d sipariş daha" % (len(liste) - 20))

    ptt = pttavm_acik()
    if ptt:
        sat += ["", "<b>PttAVM (%d) — panelden kontrol et</b>" % len(ptt)]
        for o in ptt[:10]:
            sat.append("• %s — %s %s" % (o.get("no") or "?", str(o.get("urun") or "")[:50], o.get("tutar") or ""))

    if hata:
        sat += ["", "❗ Okunamadı: " + " | ".join(hata)]
    return "\n".join(sat)


def metin_ciro():
    """24:00 TR: biten gunun (bugun degil, iş bu saatte TR takviminde zaten yeni gune gectigi
    icin dun) tum siparisleri, toplam ciro olarak."""
    an = bildirim.simdi_tr()
    gun = (an - timedelta(minutes=5)).date()  # tam gece yarisi tetiklendiginde bir onceki takvim gunu
    hepsi, hata = siparisleri_topla()
    adet, tutar, kanal = gunun_satisi(hepsi, gun.strftime("%Y-%m-%d"))
    sat = ["💰 <b>Günün cirosu</b> — %s" % gun.strftime("%d.%m.%Y"), "",
           "<b>%d sipariş · %.0f TL</b>" % (adet, tutar)]
    if kanal:
        sat.append(", ".join("%s %d" % (KANAL_AD.get(k, k), n) for k, n in sorted(kanal.items(), key=lambda x: -x[1])))
    if hata:
        sat += ["", "❗ Okunamadı: " + " | ".join(hata)]
    return "\n".join(sat)


def main():
    a = sys.argv[1:]
    if "--ciro" in a:
        metin = metin_ciro()
    else:
        metin = metin_kargo()  # varsayilan / --kargo
    try:
        print(metin)
    except UnicodeEncodeError:
        print(metin.encode("ascii", "replace").decode())
    if "--kuru" not in a:
        print(bildirim.telegram(metin))


if __name__ == "__main__":
    main()
