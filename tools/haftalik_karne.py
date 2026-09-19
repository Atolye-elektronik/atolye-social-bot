# -*- coding: utf-8 -*-
"""Haftalik kanal karnesi -> Telegram. Pazartesi 09:00 TR (cron 0 6 * * 1).

Son 7 gun vs onceki 7 gun: kanal kanal siparis adedi ve ciro, en cok satan 5 urun,
kargoya verilmemis siparisler ve kritik stok. Reklam harcamalari API'de olmadigi icin
(HB/TY/Meta/Google panel) o satir kullanicidan gelen sabit notla doldurulur.
    python tools/haftalik_karne.py --kuru
"""
import io
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [KOK, os.path.join(KOK, "src"), os.path.join(KOK, "src", "marketplaces")]
for _p in (os.path.join(KOK, ".env"),):
    if os.path.exists(_p):
        for _l in io.open(_p, encoding="utf-8"):
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from stok import bildirim, siparis  # noqa: E402
from tools.telegram_ozet import KANAL_AD, acik_mi, kritik_stoklar  # noqa: E402

GUN = 86400


def topla():
    simdi = time.time()
    bu = defaultdict(lambda: [0, 0.0]); onceki = defaultdict(lambda: [0, 0.0])
    urun = defaultdict(int); acik = []
    hata = []
    for k, fn in siparis.TOPLAYICI.items():
        try:
            L = fn() or []
        except Exception as e:
            hata.append("%s: %s" % (KANAL_AD.get(k, k), str(e)[:40])); continue
        for o in L:
            if siparis._iptal_mi(o.get("durum")):
                continue
            z = siparis._zaman(o.get("tarih"))
            if not z:
                continue
            yas = simdi - z.timestamp()
            try:
                t = float(o.get("tutar") or 0)
            except (TypeError, ValueError):
                t = 0.0
            if yas <= 7 * GUN:
                bu[k][0] += 1; bu[k][1] += t
                for kl in o.get("kalemler") or []:
                    urun[kl.get("kod") or kl.get("barkod") or "?"] += int(kl.get("adet") or 1)
            elif yas <= 14 * GUN:
                onceki[k][0] += 1; onceki[k][1] += t
            if acik_mi(o):
                acik.append((k, o))
    return bu, onceki, urun, acik, hata


def ok(a, b):
    if b == 0:
        return "yeni" if a else "-"
    d = (a - b) / b * 100
    return "%+.0f%%" % d


def metin_kur():
    bu, onceki, urun, acik, hata = topla()
    kanallar = sorted(set(bu) | set(onceki), key=lambda k: -bu[k][1])
    t_bu = sum(v[1] for v in bu.values()); n_bu = sum(v[0] for v in bu.values())
    t_on = sum(v[1] for v in onceki.values()); n_on = sum(v[0] for v in onceki.values())
    sat = ["📊 <b>Haftalik karne</b> — %s" % datetime.now().strftime("%d.%m"), "",
           "<b>Toplam: %d siparis · %.0f TL</b>  (onceki hafta %d · %.0f TL, ciro %s)" % (n_bu, t_bu, n_on, t_on, ok(t_bu, t_on)), ""]
    for k in kanallar:
        a, b = bu[k], onceki[k]
        if not a[0] and not b[0]:
            continue
        sat.append("• %s: %d sip · %.0f TL  (%s)" % (KANAL_AD.get(k, k), a[0], a[1], ok(a[1], b[1])))
    if urun:
        sat += ["", "<b>En cok satan (adet)</b>"]
        for kod, n in sorted(urun.items(), key=lambda x: -x[1])[:6]:
            sat.append("• %s ×%d" % (kod, n))
    if acik:
        sat += ["", "🚚 Kargoya verilmemis: %d (%s)" % (len(acik), ", ".join("%s %d" % (KANAL_AD.get(k, k), sum(1 for kk, _ in acik if kk == k)) for k in sorted(set(k for k, _ in acik))))]
    try:
        kr = kritik_stoklar()
        if kr:
            sat += ["", "⚠️ Kritik stok: " + ", ".join("%s=%s" % kv for kv in list(kr.items())[:20])]
    except Exception as e:
        hata.append("stok: %s" % str(e)[:40])
    sat += ["", "📣 Reklam: HB/TY/Meta/Google harcamalari panelden — 'reklam raporu' de, cikarayim."]
    if hata:
        sat += ["", "❗ Okunamadi: " + " | ".join(hata)]
    return "\n".join(sat)


if __name__ == "__main__":
    m = metin_kur()
    try:
        print(m)
    except UnicodeEncodeError:
        print(m.encode("ascii", "replace").decode())
    if "--kuru" not in sys.argv:
        print(bildirim.telegram(m))
