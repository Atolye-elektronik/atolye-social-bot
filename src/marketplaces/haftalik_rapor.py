"""Haftalık satış raporu.

Son 7 günün Trendyol siparişlerini çekip bir önceki 7 günle karşılaştırır,
özetini GitHub issue olarak açar. (Shopify ve Hepsiburada bölümleri, ilgili
API anahtarları tanımlanınca eklenecek — yapı buna hazır.)

Kullanım:  python src/marketplaces/haftalik_rapor.py
CI:        haftalik-rapor.yml — her pazartesi 07:30 TR.
"""

import datetime as dt
import time
from collections import Counter

from trendyol_client import get_orders
from issue_tracker import upsert_issue

IPTAL = {"Cancelled", "UnSupplied", "Returned"}


def _tum_paketler(start_ms, end_ms):
    paketler, page = [], 0
    while True:
        data = get_orders(start_date_ms=start_ms, end_date_ms=end_ms, page=page, size=50)
        icerik = data.get("content") or []
        paketler += icerik
        if page >= (data.get("totalPages") or 1) - 1 or not icerik:
            return paketler
        page += 1


def _ozet(paketler):
    ciro = 0.0
    adet = 0
    iptal = 0
    urunler = Counter()
    for p in paketler:
        durum = p.get("status") or p.get("shipmentPackageStatus") or ""
        if durum in IPTAL:
            iptal += 1
            continue
        for line in p.get("lines") or []:
            q = line.get("quantity") or 0
            fiyat = line.get("price") or line.get("amount") or 0
            ciro += float(fiyat) * (1 if line.get("price") else 0) or float(fiyat)
            adet += q
            urunler[(line.get("productName") or "?")[:60]] += q
    return {"paket": len(paketler), "adet": adet, "ciro": ciro, "iptal": iptal, "urunler": urunler}


def _yon(simdiki, onceki):
    if onceki == 0:
        return "—" if simdiki == 0 else "🆕"
    fark = (simdiki - onceki) / onceki * 100
    ok = "🔺" if fark > 0 else ("🔻" if fark < 0 else "➡️")
    return f"{ok} %{abs(fark):.0f}"


def main():
    simdi = int(time.time() * 1000)
    hafta = 7 * 24 * 60 * 60 * 1000
    bu = _ozet(_tum_paketler(simdi - hafta, simdi))
    gecen = _ozet(_tum_paketler(simdi - 2 * hafta, simdi - hafta))

    bugun = dt.date.today().isoformat()
    satirlar = [
        f"## Trendyol — {bugun} haftalık özet",
        "",
        "| Metrik | Bu hafta | Geçen hafta | Değişim |",
        "|---|---|---|---|",
        f"| Paket | {bu['paket']} | {gecen['paket']} | {_yon(bu['paket'], gecen['paket'])} |",
        f"| Satılan adet | {bu['adet']} | {gecen['adet']} | {_yon(bu['adet'], gecen['adet'])} |",
        f"| Brüt ciro | {bu['ciro']:.2f} TL | {gecen['ciro']:.2f} TL | {_yon(bu['ciro'], gecen['ciro'])} |",
        f"| İptal/iade paketi | {bu['iptal']} | {gecen['iptal']} | {_yon(bu['iptal'], gecen['iptal'])} |",
        "",
        "**En çok satanlar (bu hafta):**",
    ]
    for ad, q in bu["urunler"].most_common(5):
        satirlar.append(f"- {q} adet — {ad}")
    if not bu["urunler"]:
        satirlar.append("- (satış yok)")
    satirlar += [
        "",
        "_Shopify ve Hepsiburada bölümleri API anahtarları eklenince bu rapora katılacak._",
    ]
    upsert_issue(f"Haftalık satış raporu — {bugun}", "\n".join(satirlar), ["rapor"])
    print("Rapor yazıldı:", bu)


if __name__ == "__main__":
    main()
