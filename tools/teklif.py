# -*- coding: utf-8 -*-
"""Okul/ogretmen icin teklif (proforma) PDF'i uretir.

Neden var: en degerli musteri sinif paketi alan ogretmen (1.418-3.350 TL
bandinda) ama okul kartla odemiyor. Okul aile birligi / doner sermaye once
TEKLIF istiyor, onay aliyor, sonra havale ediyor. Sitede o yol yoktu.

Fiyatlar CANLI Shopify'dan cekiliyor - elle yazilmiyor, bayatlamiyor.

Kullanim:
    # once urunleri ara
    python -m tools.teklif --ara defter

    # teklif uret (kalem: handle|varyant|adet  - varyant bossa tek varyant)
    python -m tools.teklif \
        --okul "Döşemealtı Mesleki ve Teknik Anadolu Lisesi" \
        --yetkili "Ahmet Yılmaz" \
        --kalem "is-dosyasi-sinif-paketi|30 Adet|1" \
        --kalem "temrin-defteri||10"

CIKTI git disinda (teklifler/): okul ve ogretmen adi kisisel veri, depo public.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import html
import json
import pathlib
import re
import sys
import unicodedata
import urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Istanbul")
BILGI = pathlib.Path("content/teklif_bilgi.json")
CIKTI = pathlib.Path("teklifler")
LOGO = pathlib.Path("posts/media/marka/logo.png")
MAGAZA = "https://atolyeelektronik.com"


def _norm(s: str) -> str:
    s = s.replace("İ", "I").replace("ı", "i").lower()
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def _slug(s: str) -> str:
    s = _norm(s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:50] or "teklif"


def _tl(x: float) -> str:
    """1234.5 -> '1.234,50 TL'"""
    tam, _, kus = f"{x:,.2f}".partition(".")
    return f"{tam.replace(',', '.')},{kus} TL"


# ------------------------------------------------------------------ urunler

def urunleri_cek() -> list[dict]:
    r = urllib.request.Request(f"{MAGAZA}/products.json?limit=250",
                               headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(r, timeout=40) as resp:
        return json.load(resp)["products"]


def kalem_coz(urunler: list[dict], ifade: str) -> dict:
    """'handle|varyant|adet' -> {ad, varyant, adet, birim, tutar}"""
    parcalar = (ifade.split("|") + ["", ""])[:3]
    handle, varyant_ad, adet_s = [p.strip() for p in parcalar]
    if not adet_s:
        raise SystemExit(f"Kalemde adet yok: {ifade!r}  (biçim: handle|varyant|adet)")
    adet = int(adet_s)

    urun = next((u for u in urunler if u["handle"] == handle), None)
    if urun is None:
        eslesen = [u["handle"] for u in urunler if _norm(handle) in _norm(u["handle"])]
        ipucu = ("\n  Benzer: " + ", ".join(eslesen[:5])) if eslesen else ""
        raise SystemExit(f"Ürün bulunamadı: {handle!r}{ipucu}")

    varyantlar = urun["variants"]
    if varyant_ad:
        v = next((x for x in varyantlar if _norm(x["title"]) == _norm(varyant_ad)), None)
        if v is None:
            raise SystemExit(
                f"'{urun['title']}' içinde varyant yok: {varyant_ad!r}\n"
                f"  Mevcut: {', '.join(x['title'] for x in varyantlar)}")
    else:
        if len(varyantlar) > 1:
            raise SystemExit(
                f"'{urun['title']}' çok varyantlı, hangisi belirtilmeli.\n"
                f"  Mevcut: {', '.join(x['title'] for x in varyantlar)}")
        v = varyantlar[0]

    birim = float(v["price"])
    return {
        "ad": urun["title"],
        "varyant": "" if v["title"] == "Default Title" else v["title"],
        "adet": adet,
        "birim": birim,
        "tutar": birim * adet,
    }


# --------------------------------------------------------------------- html

def _html(bilgi: dict, alici: dict, kalemler: list[dict], toplam: dict,
          no: str, tarih: dt.date, gecerli: dt.date) -> str:
    s = bilgi["satici"]
    k = bilgi["kosullar"]
    o = bilgi["odeme"]
    e = html.escape

    satirlar = "".join(
        f"<tr><td class='ad'>{e(x['ad'])}"
        f"{'<span class=var>' + e(x['varyant']) + '</span>' if x['varyant'] else ''}</td>"
        f"<td class='sag'>{x['adet']}</td>"
        f"<td class='sag'>{_tl(x['birim'])}</td>"
        f"<td class='sag tutar'>{_tl(x['tutar'])}</td></tr>"
        for x in kalemler
    )

    kargo_satiri = (
        f"<tr><td>Kargo</td><td class='sag ucretsiz'>Ücretsiz</td></tr>"
        if toplam["kargo_bedava"] else
        f"<tr><td>Kargo</td><td class='sag'>Ödeme adımında hesaplanır</td></tr>"
    )

    odeme_blok = (
        f"<div class='kutu'><h3>Ödeme</h3>"
        f"<p><b>{e(o['hesap_sahibi'])}</b><br>{e(o['banka'])}<br>"
        f"<span class='iban'>{e(o['iban'])}</span></p></div>"
        if o.get("iban") else
        "<div class='kutu eksik'><h3>Ödeme</h3>"
        "<p>Banka bilgileri eklenmedi — <b>bu teklif gönderilmeden önce "
        "content/teklif_bilgi.json içindeki IBAN doldurulmalı.</b></p></div>"
    )

    notlar = "".join(f"<li>{e(n)}</li>" for n in k["notlar"])

    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<style>
  /* Kenar bosluklarini @page'e birakma: Chromium'da pdf() margin parametresi
     onu eziyor ve belge kagit kenarina yapisik cikabiliyor. Bosluk body
     dolgusunda tutuluyor, pdf() margin=0 ile basiliyor - hem PDF hem PNG
     onizleme ayni gorunuyor. */
  @page {{ size: A4; margin: 0; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: "Segoe UI", "DejaVu Sans", Arial, sans-serif;
          color: #16202e; font-size: 10.5pt; margin: 0;
          padding: 14mm 14mm 12mm; }}
  .ust {{ display: flex; justify-content: space-between; align-items: flex-start;
          border-bottom: 3px solid #0f6e64; padding-bottom: 12px; }}
  .marka h1 {{ margin: 0 0 4px; font-size: 19pt; letter-spacing: .5px; }}
  .marka p {{ margin: 1px 0; font-size: 8.8pt; color: #55617a; line-height: 1.45; }}
  .belge {{ text-align: right; }}
  .belge h2 {{ margin: 0 0 6px; font-size: 13pt; color: #0f6e64;
               letter-spacing: 1.5px; }}
  .belge p {{ margin: 1px 0; font-size: 9pt; color: #55617a; }}
  .belge b {{ color: #16202e; }}
  .alici {{ margin: 18px 0 14px; background: #f4f7f9; border-radius: 6px;
            padding: 12px 14px; }}
  .alici h3 {{ margin: 0 0 6px; font-size: 8.5pt; letter-spacing: 1.2px;
               color: #55617a; text-transform: uppercase; }}
  .alici p {{ margin: 0; font-size: 11.5pt; font-weight: 600; }}
  .alici span {{ display: block; font-size: 9.5pt; font-weight: 400;
                 color: #55617a; margin-top: 2px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 6px; }}
  th {{ background: #0f6e64; color: #fff; font-size: 8.6pt; letter-spacing: .8px;
        text-transform: uppercase; padding: 8px 10px; text-align: left; }}
  td {{ padding: 9px 10px; border-bottom: 1px solid #e6eaf0; vertical-align: top; }}
  .sag {{ text-align: right; white-space: nowrap; }}
  .ad {{ font-weight: 600; }}
  .var {{ display: block; font-weight: 400; font-size: 9pt; color: #55617a; }}
  .tutar {{ font-weight: 700; }}
  .alt {{ display: flex; gap: 16px; margin-top: 16px; align-items: flex-start; }}
  .alt > div {{ flex: 1; }}
  .ozet table {{ margin: 0; }}
  .ozet td {{ border: none; padding: 5px 0; font-size: 10pt; }}
  .ozet .genel td {{ border-top: 2px solid #16202e; padding-top: 9px;
                     font-size: 12.5pt; font-weight: 700; }}
  .ucretsiz {{ color: #0f6e64; font-weight: 700; }}
  .kutu {{ background: #f4f7f9; border-radius: 6px; padding: 11px 13px; }}
  .kutu.eksik {{ background: #fff4e5; border: 1px solid #e0a94a; }}
  .kutu h3 {{ margin: 0 0 5px; font-size: 8.5pt; letter-spacing: 1.2px;
              color: #55617a; text-transform: uppercase; }}
  .kutu p {{ margin: 0; font-size: 9.5pt; line-height: 1.6; }}
  .iban {{ font-family: "DejaVu Sans Mono", Consolas, monospace;
           letter-spacing: .5px; }}
  ul {{ margin: 8px 0 0; padding-left: 16px; font-size: 9pt; color: #55617a;
        line-height: 1.7; }}
  .dip {{ margin-top: 16px; border-top: 1px solid #e6eaf0; padding-top: 9px;
          font-size: 8.5pt; color: #7a869c; display: flex;
          justify-content: space-between; }}
</style></head><body>

<div class="ust">
  <div class="marka">
    <h1>{e(s['unvan'])}</h1>
    <p>{e(s['adres'])}</p>
    <p>{e(s['telefon'])} &nbsp;·&nbsp; {e(s['eposta'])}</p>
    <p>{e(s['site'])} &nbsp;·&nbsp; Vergi No: {e(s['vergi_no'])}</p>
  </div>
  <div class="belge">
    <h2>TEKLİF</h2>
    <p>No: <b>{e(no)}</b></p>
    <p>Tarih: <b>{tarih.strftime('%d.%m.%Y')}</b></p>
    <p>Geçerlilik: <b>{gecerli.strftime('%d.%m.%Y')}</b></p>
  </div>
</div>

<div class="alici">
  <h3>Sayın</h3>
  <p>{e(alici['okul'])}
    {'<span>' + e(alici['yetkili']) + '</span>' if alici.get('yetkili') else ''}
  </p>
</div>

<table>
  <thead><tr><th>Ürün</th><th class="sag">Adet</th>
  <th class="sag">Birim Fiyat</th><th class="sag">Tutar</th></tr></thead>
  <tbody>{satirlar}</tbody>
</table>

<div class="alt">
  <div>
    {odeme_blok}
    <ul>{notlar}<li>{e(k['teslim'])}</li></ul>
  </div>
  <div class="ozet">
    <table>
      <tr><td>Ara toplam (KDV hariç)</td><td class="sag">{_tl(toplam['matrah'])}</td></tr>
      <tr><td>KDV (%{k['kdv_orani']})</td><td class="sag">{_tl(toplam['kdv'])}</td></tr>
      {kargo_satiri}
      <tr class="genel"><td>GENEL TOPLAM</td>
          <td class="sag">{_tl(toplam['genel'])}</td></tr>
    </table>
  </div>
</div>

<div class="dip">
  <span>Bu belge bir teklif olup fatura yerine geçmez.</span>
  <span>{e(s['unvan'])} · {e(s['site'])}</span>
</div>
</body></html>"""


async def _pdf_yaz(html_metin: str, hedef: pathlib.Path,
                   onizleme: bool = False) -> None:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 794, "height": 1123})  # A4 @96dpi
        await pg.set_content(html_metin, wait_until="load")
        await pg.pdf(path=str(hedef), format="A4", print_background=True,
                     margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        if onizleme:
            await pg.screenshot(path=str(hedef.with_suffix(".png")), full_page=True)
        await b.close()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ara", help="ürün ara (handle ve varyantları listeler)")
    p.add_argument("--okul")
    p.add_argument("--yetkili", default="")
    p.add_argument("--kalem", action="append", default=[],
                   help="handle|varyant|adet  (tekrarlanabilir)")
    p.add_argument("--no", help="teklif no (varsayılan: YYYYMMDD-XX)")
    p.add_argument("--onizleme", action="store_true",
                   help="PDF yaninda PNG onizleme de yaz")
    a = p.parse_args()

    urunler = urunleri_cek()

    if a.ara:
        for u in urunler:
            if _norm(a.ara) not in _norm(u["title"]):
                continue
            print(f"\n{u['title']}\n  handle: {u['handle']}")
            for v in u["variants"]:
                ad = "(tek varyant)" if v["title"] == "Default Title" else v["title"]
                print(f"    {ad:<24} {float(v['price']):>10,.2f} TL")
        return

    if not a.okul or not a.kalem:
        raise SystemExit("--okul ve en az bir --kalem gerekli. Ürün için: --ara defter")

    bilgi = json.loads(BILGI.read_text(encoding="utf-8"))
    k = bilgi["kosullar"]

    kalemler = [kalem_coz(urunler, x) for x in a.kalem]
    ara = sum(x["tutar"] for x in kalemler)          # KDV dahil (Shopify fiyatlari)
    oran = k["kdv_orani"] / 100
    matrah = ara / (1 + oran)
    toplam = {
        "matrah": matrah,
        "kdv": ara - matrah,
        "genel": ara,
        "kargo_bedava": ara >= k["ucretsiz_kargo_esigi"],
    }

    bugun = dt.datetime.now(TZ).date()
    gecerli = bugun + dt.timedelta(days=k["gecerlilik_gun"])
    no = a.no or f"{bugun.strftime('%Y%m%d')}-{abs(hash(a.okul)) % 90 + 10}"

    CIKTI.mkdir(parents=True, exist_ok=True)
    hedef = CIKTI / f"{no}-{_slug(a.okul)}.pdf"
    metin = _html(bilgi, {"okul": a.okul, "yetkili": a.yetkili},
                  kalemler, toplam, no, bugun, gecerli)
    asyncio.run(_pdf_yaz(metin, hedef, a.onizleme))

    print(f"Teklif: {hedef}")
    for x in kalemler:
        ad = f"{x['ad']}" + (f" / {x['varyant']}" if x['varyant'] else "")
        print(f"  {x['adet']:>3} x {ad[:52]:<54}{_tl(x['tutar']):>14}")
    print(f"  {'GENEL TOPLAM':>60}{_tl(toplam['genel']):>14}")
    if toplam["kargo_bedava"]:
        print(f"  kargo ücretsiz ({k['ucretsiz_kargo_esigi']} TL üzeri)")
    else:
        eksik = k["ucretsiz_kargo_esigi"] - toplam["genel"]
        print(f"  UYARI: ücretsiz kargoya {_tl(eksik)} kalmış")
    if not bilgi["odeme"].get("iban"):
        print("  UYARI: IBAN bos - content/teklif_bilgi.json doldurulmadan gonderme")


if __name__ == "__main__":
    main()
