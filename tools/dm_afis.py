# -*- coding: utf-8 -*-
"""Instagram DM'inde gonderilen, urun fotografli afisleri uretir.

Neden afis: bilinmeyen bir hesaptan gelen ciplak CDN linki oltalama gibi
duruyor ve tiklanmiyor. Gorsel uygulama icinde aciliyor, risk yok, teklif
aninda goruluyor. Link ancak karsi taraf ilgilendigini belirtince gonderilir.

Uc segment, uc afis:
  01-okul.png     MTAL     temrin defteri + is dosyasi, sinif paketi kademeleri
  02-mesem.png    MESEM    yalnizca is dosyasi (atolye yok, ogrenci isletmede)
  03-robotik.png  BILSEM   Arduino ve atolye malzemesi

Fiyat ya da kampanya degisince bu betigi calistir, gorseller yeniden uretilir.

    python tools/dm_afis.py
"""

import html, pathlib, sys
sys.path.insert(0, ".")
from src.karusel_gorsel import Cizer

CIKTI = pathlib.Path("pazarlama/afis")
CIKTI.mkdir(parents=True, exist_ok=True)
def K(t): return html.escape(str(t), quote=False)

# Fotograf alani icin ek stil: iki fotograf yan yana da sigsin.
EK_STIL = """
<style>
.fotolar{display:flex;gap:18px;margin-top:26px;flex:1;min-height:0}
.fotokart{flex:1;background:#fff;border:2px solid #D8D0C6;border-radius:10px;
 display:flex;align-items:center;justify-content:center;padding:20px;min-height:0}
.fotokart img{max-width:100%;max-height:100%;object-fit:contain}
.kampanya{display:flex;align-items:baseline;gap:14px;margin-top:22px;padding:18px 24px;
 background:#F4E7DA;border:2px solid #8E4A18;border-radius:7px}
.kampanya .kod{font-family:"DejaVu Sans Mono",monospace;font-size:38px;font-weight:700;color:#8E4A18}
.kampanya .aciklama{font-size:26px;color:#4A423A;line-height:1.3}
.mini{display:flex;gap:14px;margin-top:18px}
.mini .kutu{flex:1;background:#fff;border:2px solid #D8D0C6;border-radius:6px;
 padding:14px 16px;text-align:center}
.mini .adet{font-size:30px;font-weight:700}
.mini .tutar{font-size:30px;font-weight:700;color:#8E4A18;
 font-family:"DejaVu Sans Mono",monospace;margin-top:4px}
.mini .birim{font-size:20px;color:#7A7168;margin-top:4px}
.katalog{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:26px;flex:1;min-height:0}
.urun{background:#fff;border:2px solid #D8D0C6;border-radius:10px;padding:16px;
 display:flex;flex-direction:column;min-height:0}
.urun .gorsel{flex:1;min-height:0;display:flex;align-items:center;justify-content:center}
.urun .gorsel img{max-width:100%;max-height:100%;object-fit:contain}
.urun .ad{font-size:26px;font-weight:700;margin-top:12px;line-height:1.25}
.urun .fi{font-size:30px;font-weight:700;color:#8E4A18;margin-top:6px;
 font-family:"DejaVu Sans Mono",monospace}
.urun .fi small{font-size:20px;color:#7A7168;font-weight:400;font-family:"DejaVu Sans",sans-serif}
</style>
"""

def afis(cizer, kicker, baslik, alt, fotolar, kademeler, maddeler, foot_sol, dosya):
    f_html = "".join(f'<div class="fotokart"><img src="{html.escape(u, quote=True)}" alt=""></div>'
                     for u in fotolar)
    k_html = ""
    if kademeler:
        k_html = '<div class="mini">' + "".join(
            f'<div class="kutu"><div class="adet">{K(a)}</div>'
            f'<div class="tutar">{K(t)}</div><div class="birim">{K(b)}</div></div>'
            for a, t, b in kademeler) + "</div>"
    m_html = ("<ul>" + "".join(f"<li>{K(m)}</li>" for m in maddeler) + "</ul>") if maddeler else ""

    govde = (
        EK_STIL
        + f'<div class="kicker">{K(kicker)}</div><h2>{K(baslik)}</h2>'
        + (f'<div class="sub">{K(alt)}</div>' if alt else "")
        + (f'<div class="fotolar">{f_html}</div>' if f_html else "")
        + k_html + m_html
        # ATOLYE10 bilerek yok: o kod online sepette calisiyor, okul siparisleri
        # ise proforma + havale ile geliyor ve indirim elle uygulanmayacak.
        # Karsilanamayacak vaat ilk temasta guven kaybi olur. Onun yerine her
        # kanalda gecerli olan kargo esigi yaziliyor.
        + '<div class="kampanya"><span class="kod">KARGO BİZDEN</span>'
          '<span class="aciklama">1.200 ₺ ve üzeri<br>tüm okul siparişlerinde</span></div>'
        + f'<div class="foot"><span>{K(foot_sol)}</span><b>0546 825 32 10</b></div>'
    )
    return cizer._uret(govde, CIKTI / dosya)

C = "https://cdn.shopify.com/s/files/1/0801/9692/7717/files/"
TEMRIN = C + "1.webp?v=1784792321"
ISDOSYA = C + "isdosyasi1_377200c3-0c47-452a-9bde-8c9dcd1ac333.webp?v=1784792291"
ARDUINO = C + "Baslangicseti.png?v=1785260927"
DENEY   = C + "temelelektronik.png?v=1785263627"
CANTA   = C + "Takimcantasi.png?v=1785258195"
ENDUSTRI = C + "EndElkSeti.png?v=1785182931"

KADEME = [("10 Adet", "833 ₺", "83,30/adet"),
          ("20 Adet", "1.649 ₺", "82,45/adet"),
          ("30 Adet", "2.473,50 ₺", "82,45/adet")]

def katalog_afis(cizer, dosya):
    """MTAL katalog afisi: dort urun grubu tek gorselde, 2x2."""
    urunler = [
        (TEMRIN,  "Temrin Defteri · İş Dosyası", "adedi 85 ₺", " — 30'lu sınıf paketi 2.473,50 ₺"),
        (CANTA,   "Takım Çantası Setleri", "1.076 ₺", "'den — 17 parça full set 1.911 ₺"),
        (ARDUINO, "Arduino Eğitim Setleri", "782 ₺", "'den — ileri seviye 1.588 ₺"),
        (ENDUSTRI,"Endüstriyel Elektronik Seti", "659 ₺", "'den — 11. sınıf müfredatına göre"),
    ]
    kartlar = "".join(
        f'<div class="urun"><div class="gorsel"><img src="{html.escape(u, quote=True)}" alt=""></div>'
        f'<div class="ad">{K(a)}</div><div class="fi">{K(f)}<small>{K(n)}</small></div></div>'
        for u, a, f, n in urunler)
    govde = (
        EK_STIL
        + '<div class="kicker">2026 – 2027 EĞİTİM YILI</div>'
        + "<h2>Atölyeniz için tek listede</h2>"
        + f'<div class="katalog">{kartlar}</div>'
        + '<div class="kampanya"><span class="kod">KARGO BİZDEN</span>'
          '<span class="aciklama">1.200 ₺ ve üzeri<br>tüm okul siparişlerinde</span></div>'
        + '<div class="foot"><span>atolyeelektronik.com/pages/okul-siparisi</span>'
          "<b>0546 825 32 10</b></div>"
    )
    return cizer._uret(govde, CIKTI / dosya)



with Cizer() as c:
    afis(c, "2026 – 2027 EĞİTİM YILI", "Okullara ve öğretmenlere özel fiyat",
         "Temrin defteri ve iş dosyası — adedi 85 ₺, sınıf paketinde birim fiyat düşüyor.",
         [TEMRIN, ISDOSYA], KADEME, [],
         "atolyeelektronik.com/pages/okul-siparisi", "01-okul.png")

    afis(c, "MESLEKİ EĞİTİM MERKEZLERİ", "İşletmelerde Mesleki Eğitim İş Dosyası",
         "MEB müfredatına ve staj yönetmeliğine uyumlu. A4, tel dikişli.",
         [ISDOSYA], KADEME, [],
         "atolyeelektronik.com/pages/okul-siparisi", "02-mesem.png")

    afis(c, "ATÖLYE MALZEMESİ", "Robotik ve elektronik atölyeleri için",
         "Arduino başlangıç setinden bitirme projesi kitine kadar tek listede.", [ARDUINO], [],
         ["Arduino setleri, sensör ve motor sürücü modülleri",
          "Breadboard, jumper kablo, sarf malzeme",
          "Takım çantası setleri · Bitirme projesi kitleri"],
         "atolyeelektronik.com/pages/okul-siparisi", "03-robotik.png")

    katalog_afis(c, "04-mtal-katalog.png")

for p in sorted(CIKTI.glob("*.png")):
    print(f"  {p.name}  {p.stat().st_size//1024} KB")
