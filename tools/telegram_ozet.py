# -*- coding: utf-8 -*-
"""Gunluk Telegram ozeti: bugunku satislar + kargoya verilmemis siparisler + kritik stok.

Sabah 09:00 ve aksam 18:00'de (TR) calisir; siparis basina bildirimden AYRIDIR.
    python tools/telegram_ozet.py            # ekrana basar + Telegram'a gonderir
    python tools/telegram_ozet.py --kuru     # yalniz ekrana basar
"""
import io
import os
import sys
from datetime import datetime, timedelta

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [KOK, os.path.join(KOK, "src"), os.path.join(KOK, "src", "marketplaces")]

for _p in (os.path.join(KOK, ".env"),):          # yerelde calistirinca anahtarlari yukle
    if os.path.exists(_p):
        for _l in io.open(_p, encoding="utf-8"):
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from stok import bildirim, merkez, siparis  # noqa: E402
from stok.recete import Recete  # noqa: E402

# Bu kelimeler durumda geciyorsa is bitmis demektir; gerisi "kargoya verilmedi".
KAPALI = ("ship", "deliver", "teslim", "fulfil", "cancel", "iptal", "iade", "return", "unsupplied", "refund")
ACIK_ZORLA = ("unfulfilled", "unshipped", "unpacked", "partially_fulfilled", "partially fulfilled",
              "shipment_picking", "picking", "hazirlan", "hazırlan")  # Idefix "shipment_picking" icinde "ship" geciyor
# Kanal durumunu insan diline cevir: "neden hala listede?" sorusunun cevabi.
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


def bugunku_satis(hepsi):
    """Bugun gelen siparis sayisi ve cirosu (iptaller haric)."""
    bugun = datetime.now().strftime("%Y-%m-%d")
    adet, tutar, kanal = 0, 0.0, {}
    for k, L in hepsi.items():
        for o in L:
            t = siparis._zaman(o.get("tarih"))
            if not t or t.strftime("%Y-%m-%d") != bugun:
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


def kritik_stoklar(esik=None):
    esik = merkez.KRITIK_ESIK if esik is None else esik
    R = Recete()
    parca = merkez.parca_stoklari()
    hedef = merkez.hedef_stoklar(R, parca)
    return {k: v for k, v in sorted(hedef.items()) if isinstance(v, int) and v <= esik}


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


def metin_kur():
    an = datetime.now()
    hepsi, hata = siparisleri_topla()
    sat = ["📋 <b>%s ozeti</b> — %s" % ("Sabah" if an.hour < 12 else "Aksam", an.strftime("%d.%m %H:%M")), ""]

    adet, tutar, kanal = bugunku_satis(hepsi)
    sat.append("💰 <b>Bugun: %d siparis · %.0f TL</b>%s" % (
        adet, tutar, ("  (" + ", ".join("%s %d" % (KANAL_AD.get(k, k), n) for k, n in sorted(kanal.items(), key=lambda x: -x[1])) + ")") if kanal else ""))

    acik = {k: [o for o in L if acik_mi(o)] for k, L in hepsi.items()}
    toplam = sum(len(v) for v in acik.values())
    sat += ["", "🚚 <b>Kargoya verilmemis: %d siparis</b>" % toplam]
    for k, liste in acik.items():
        if not liste:
            continue
        sat.append("\n<b>%s (%d)</b>" % (KANAL_AD.get(k, k), len(liste)))
        for o in sorted(liste, key=lambda x: str(x.get("tarih")))[:12]:
            t = siparis._zaman(o.get("tarih"))
            d = str(o.get("durum") or "").lower()
            aciklama = DURUM_AD.get(d, o.get("durum") or "")
            sat.append("• %s %s — %s <i>(%s)</i>" % (t.strftime("%d.%m") if t else "", o.get("no"),
                                                     kalem_metni(o)[:70], aciklama))
        if len(liste) > 12:
            sat.append("• ... +%d siparis daha" % (len(liste) - 12))

    ptt = pttavm_acik()
    if ptt:
        sat += ["", "<b>PttAVM (%d) — panelden kontrol et</b>" % len(ptt)]
        for o in ptt[:8]:
            sat.append("• %s — %s %s" % (o.get("no") or "?", str(o.get("urun") or "")[:50], o.get("tutar") or ""))
    try:
        kritik = kritik_stoklar()
        if kritik:
            sat += ["", "⚠️ <b>Kritik stok (%d)</b>" % len(kritik),
                    ", ".join("%s=%s" % (k, v) for k, v in list(kritik.items())[:40])]
    except Exception as e:
        hata.append("stok: %s" % str(e)[:50])
    if hata:
        sat += ["", "❗ Okunamadi: " + " | ".join(hata)]
    return "\n".join(sat)


def main():
    metin = metin_kur()
    try:
        print(metin)
    except UnicodeEncodeError:
        print(metin.encode("ascii", "replace").decode())
    if "--kuru" not in sys.argv:
        print(bildirim.telegram(metin))


if __name__ == "__main__":
    main()
