# -*- coding: utf-8 -*-
"""Defter aciklamalarini TY'deki TEKLI aciklamadan turetir.

Kullanici kurali (27.08.2026):
  - Tekli aciklamalar zaten iyi; KISALTMA. Sadece yaprak/sayfa bilgisi eklenir.
  - Sinif paketleri ayni metni alir; ustune paket icerigi ve diger secenekler.
  - Pazaryeri kurali: kendi sitemiz / kampanya / kupon ANILMAZ.

Tekli metinler TY'den okunur (tools/ty_tekli_aciklama.json ya da canli API).
"""
from __future__ import annotations

import re

YAPRAK = {"isdosyasi": (32, 64), "temrin": (48, 96)}
SECENEKLER = ["tekli", "10'lu", "20'li", "30'lu"]

AILE = {
    "AESTJDFTR": "isdosyasi", "AEISDSYS10": "isdosyasi", "AEISDSYS20": "isdosyasi",
    "AEISDP10": "isdosyasi", "AEISDP20": "isdosyasi", "AEISD30": "isdosyasi",
    "AETEMDEF": "temrin", "AETMRNDFTR10": "temrin", "AETMRNDFTR20": "temrin",
    "AETMRNDFTR30": "temrin", "AETMR10": "temrin", "AETMRP20": "temrin",
    "AETMRP30": "temrin",
}
PAKET = {
    "AESTJDFTR": "tekli", "AETEMDEF": "tekli",
    "AEISDSYS10": "10'lu", "AEISDSYS20": "20'li",
    "AEISDP10": "10'lu", "AEISDP20": "20'li", "AEISD30": "30'lu",
    "AETMRNDFTR10": "10'lu", "AETMRNDFTR20": "20'li", "AETMRNDFTR30": "30'lu",
    "AETMR10": "10'lu", "AETMRP20": "20'li", "AETMRP30": "30'lu",
}
URUN_ADI = {"isdosyasi": "İşletmelerde Mesleki Eğitim İş Dosyası",
            "temrin": "Temrin Defteri"}


def _digerleri(kendisi: str) -> str:
    kalan = [s for s in SECENEKLER if s != kendisi]
    return ", ".join(kalan[:-1]) + " ve " + kalan[-1]


def yaprak_ekle(html: str, aile: str) -> str:
    """Tekli aciklamaya yaprak/sayfa bilgisini ekler (varsa zenginlestirir)."""
    yaprak, sayfa = YAPRAK[aile]
    # Zaten 'NN Yaprak' geciyorsa sayfa sayisini yanina yaz.
    desen = re.compile(rf"{yaprak}\s*Yaprak", re.IGNORECASE)
    if desen.search(html):
        return desen.sub(f"{yaprak} Yaprak ({sayfa} Sayfa)", html, count=1)
    # Gecmiyorsa ozellikler basligindan hemen sonra yeni madde ekle.
    yeni = (f"<p><span><b>Sayfa Yapısı:</b></span><span> A4 boyut, {yaprak} yaprak "
            f"({sayfa} sayfa)</span></p>")
    # "Ozellikler" basligindan sonra ekle; yoksa ilk <ul>'in basina.
    m = re.search(r"<h3[^>]*>[^<]*(?:Özellik|Ozellik)[^<]*</h3>", html, re.IGNORECASE)
    if m:
        i = m.end()
        return html[:i] + " " + yeni + html[i:]
    m = re.search(r"<ul[^>]*>", html)
    if m:
        i = m.start()
        return html[:i] + yeni + html[i:]
    return html.replace("</div>", yeni + "</div>", 1)


def paket_bloklari(stok_kodu: str) -> str:
    aile, paket = AILE[stok_kodu], PAKET[stok_kodu]
    ad = URUN_ADI[aile]
    p = []
    if paket != "tekli":
        adet = paket.split("'")[0]
        kim = ("koordinatör öğretmen veya bölüm şefinin" if aile == "isdosyasi"
               else "atölye öğretmeni veya bölüm şefinin")
        p.append("<h3>Sınıf Paketi</h3>")
        p.append(f"<p><b>Paket içeriği:</b> {adet} adet {ad}.</p>")
        p.append(f"<p>Sınıf paketi, {kim} sınıfın tamamını tek siparişte temin "
                 f"etmesi için hazırlanmıştır.</p>")
    p.append(f"<p>Bu üründe {_digerleri(paket)} seçeneklerimiz de mevcuttur.</p>")
    return "".join(p)


def tekli_paket_cumlesi_sil(html: str) -> str:
    """Tekli metindeki "Paket Iceriginde 1 adet ... bulunmaktadir." cumlesini atar.

    Sinif paketlerinde bu cumle "Paket icerigi: 10 adet" satiriyla celisiyor;
    musteri hangisine inanacagini bilemez.
    """
    return re.sub(r"\s*Paket İçeriğinde\s*1\s*adet[^<.]*\.", "", html)


def metin(stok_kodu: str, tekli_html: str) -> str:
    """tekli_html: ilgili ailenin TY'deki tekli urun aciklamasi (ham HTML)."""
    aile = AILE[stok_kodu]
    govde = yaprak_ekle(tekli_html, aile)
    if PAKET[stok_kodu] != "tekli":
        govde = tekli_paket_cumlesi_sil(govde)
    ek = paket_bloklari(stok_kodu)
    # Kapanis </div></div> oncesine ekle
    i = govde.rfind("</div>")
    i = govde.rfind("</div>", 0, i)
    if i == -1:
        return govde + ek
    return govde[:i] + ek + govde[i:]
