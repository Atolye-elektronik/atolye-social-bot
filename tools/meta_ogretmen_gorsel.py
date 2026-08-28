# -*- coding: utf-8 -*-
"""Meta reklamları için öğretmene yönelik görseller üretir.

Neden ayrı bir araç: elimizdeki 53 video ve carousel slaytı ÖĞRENCİYE
sesleniyor — ürünü anlatıyor. Öğretmen mesajı bambaşka: ürünü değil **çözümü**
anlatır ("tüm sınıf, tek sipariş, tek fatura").

İki tasarım kararı, ikisi de kullanıcı uyarısıyla düzeltildi:
  * **Açık zemin.** Facebook akışı beyaz; koyu görsel orada ağır duruyor ve
    öğretmen kitlesine kurumsal görünmek istiyoruz. Marka renkleri aynı,
    yalnız roller yer değiştirdi — lacivert artık zemin değil METİN.
  * **Ürün fotoğrafı ana öğe.** Akışta durduran şey fotoğraftır; salt metin
    kart kaydırılıp geçilir. Metin kısa tutuldu, işi fotoğraf yapıyor.

Kitleyi görselin kendisi eliyor: üstteki turuncu şerit doğrudan "MESLEKİ VE
TEKNİK ANADOLU LİSELERİ İÇİN" diyor — ürünler bu okulların müfredatına göre
hazırlandı, genel liseye gösterilen her gösterim boşa gidiyor. Meta'da meslek hedeflemesi kalmadığı için
(bkz. meta-ads-kurulum.md) eleme işini yaratıcı yapıyor.

    python tools/meta_ogretmen_gorsel.py
"""

from __future__ import annotations

import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw  # noqa: E402

from src.carousel_gorsel import (  # noqa: E402
    ALTIN, BEYAZ, TURUNCU, H, W,
    _aralikli, _aralikli_genislik, _bold, _devre_izi, _indir, _kaydet,
    _mono, _normal, _sigdir,
)

SERIT = "MESLEKİ VE TEKNİK ANADOLU LİSELERİ İÇİN"
MARKA = "ATÖLYE ELEKTRONİK"
SITE = "atolyeelektronik.com"

ZEMIN = (245, 248, 250)      # saf beyaz değil — akışta kaybolmasın
LACIVERT = (11, 20, 32)      # başlık
TEAL = (13, 132, 124)        # turkuazın açık zeminde okunan tonu
GRI = (104, 120, 136)

CDN = "https://cdn.shopify.com/s/files/1/0801/9692/7717/files/"

# Fiyatlar 28.08'de %11,2 zam sonrası Shopify'dan alındı (ATOLYE10 %10
# kuponunu nötrleyen oran). Fiyat rozeti bilerek var: satış
# görselinde rakam görmeyen kullanıcı tıklamıyor, fiyatı merak edip kaydırıyor.
# Defterde birim "öğrenci başına" — öğretmenin karar verdiği birim bu, 2.751 TL
# yerine 85 TL görmek kararı kolaylaştırıyor. Defter paketlerinde adet başı
# sabit 85 TL (tekli 90).
#
# Toptan indirimi YALNIZ defterlerde açık fiyatla veriliyor (kullanıcı 28.08).
# Diğer ürünlerde adede göre özel fiyat konuşuluyor; görselde sabit bir oran
# yazmak sonradan pazarlık alanını kapatıyor.
TOPTAN = "Toplu alımda özel fiyat · bize yazın"
REKLAMLAR = [
    # Staj defteri ve temrin defteri AYRI reklama cikiyor (kullanici 28.08):
    # farkli urunler, farkli arama terimleri, farkli ders baglami. Tek
    # "defterler" reklami ikisini de bulanik anlatiyordu.
    {
        "dosya": "meta-ogretmen-staj-defteri.png",
        # Staj defteri tek okul turune ait degil: MTAL, MESEM ve ciraklik
        # egitimi ogrencilerinin hepsi ayni is dosyasini tutuyor.
        "serit": "MESLEK LİSESİ · MESEM · ÇIRAKLIK İÇİN",
        "foto": "kaynak/staj-defteri.jpg",
        "rozet_fiyat": "öğrenci başına 85 TL",
        "baslik": "Staj defteri, tek siparişte",
        "destek": "Tek fatura · tek kargo · aynı gün gönderim",
        "fiyatlar": [("1 adet", "90 TL"), ("10 adet", "850 TL"),
                     ("20 adet", "1.700 TL"), ("30 adet", "2.550 TL")],
        "toptan": None,
    },
    {
        "dosya": "meta-ogretmen-temrin-defteri.png",
        "foto": "kaynak/temrin-defteri.jpg",
        "rozet_fiyat": "öğrenci başına 85 TL",
        "baslik": "Temrin defteri, tek siparişte",
        "destek": "48 yaprak 96 sayfa · tek fatura · aynı gün kargo",
        "fiyatlar": [("1 adet", "90 TL"), ("10 adet", "850 TL"),
                     ("20 adet", "1.700 TL"), ("30 adet", "2.550 TL")],
        "toptan": None,
    },
    {
        "dosya": "meta-ogretmen-takim-cantasi.png",
        "foto": CDN + "Takimcantasi.png?v=1785258195",
        "rozet_fiyat": "1.990 TL",
        "baslik": "Atölye dersine hazır sınıf",
        "destek": "Pense, havya, multimetre, lehim takımı",
        "fiyatlar": [("17 parça tam set", "1.990 TL")],
        "toptan": TOPTAN,
    },
    {
        "dosya": "meta-ogretmen-endustriyel.png",
        "foto": CDN + "EndElkhepsi.webp?v=1782335968",
        "rozet_fiyat": "699 TL",
        "baslik": "Endüstriyel Elektronik dersi, 11. sınıf",
        "destek": "Müfredattaki uygulamalar birebir, tek sette",
        "fiyatlar": [("Tam set", "699 TL")],
        "toptan": TOPTAN,
    },
    {
        "dosya": "meta-ogretmen-arduino.png",
        "foto": CDN + "Baslangicseti.png?v=1785260927",
        "rozet_fiyat": "769 TL",
        "baslik": "Mikrodenetleyiciler ve Robotik Kodlama",
        "destek": "Türkçe kaynak ve devre örnekleriyle",
        "fiyatlar": [("46 parça", "769 TL"), ("56 parça", "1.092 TL"),
                     ("88 parça", "1.766 TL")],
        "toptan": TOPTAN,
    },
    # MESEM ayrı kurum türü, ayrı reklam seti. Staj defteri MTAL'de de
    # satılıyor (kullanıcı 28.08) — bu onun yerine değil, yanına geliyor.
    # MESEM'de işletmede mesleki eğitim modelin kendisi olduğu için iş
    # dosyası ihtiyacı öğrencilerin tamamını kapsıyor.
    {
        "dosya": "meta-mesem-staj-defteri.png",
        "serit": "MESLEKİ EĞİTİM MERKEZİ · MESEM İÇİN",
        "foto": "kaynak/staj-defteri.jpg",
        "rozet_fiyat": "öğrenci başına 85 TL",
        "baslik": "MESEM staj defteri",
        "destek": "İşletmelerde mesleki eğitim iş dosyası",
        "fiyatlar": [("1 adet", "90 TL"), ("10 adet", "850 TL"),
                     ("20 adet", "1.700 TL"), ("30 adet", "2.550 TL")],
        "toptan": None,
    },
]

ACELE = "OKULLAR 14 EYLÜL'DE AÇILIYOR"
CTA = "Hemen Sipariş Ver"

# Turuncu aciliyet şeridi bunun altına giriyor; CTA düğmesinin üst kenarı
# 1172px. Metin bloğu bu tabanı geçerse şerit metnin üstüne biniyor.
METIN_TABANI = 1096

CIKTI_DIZIN = pathlib.Path(__file__).resolve().parents[1] / "posts" / "media" / "meta-ogretmen"
LOGO = pathlib.Path(__file__).resolve().parents[1] / "posts" / "media" / "marka" / "logo.png"
LOGO_BOY = 340          # arka plana yedirilen filigran

# Fotograf kartinin yerlesimi
KART = (70, 232, W - 70, 736)


def _zemin_ac(seed: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Açık zemin + soluk devre izleri.

    İzler ayrı katmana çizilip düşük opaklıkla bindiriliyor; doğrudan
    çizilince açık zeminde baskın çıkıp metnin önüne geçiyorlar.
    """
    tuval = Image.new("RGB", (W, H), ZEMIN)
    katman = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    kd = ImageDraw.Draw(katman)
    rnd = random.Random(seed)
    _devre_izi(kd, rnd, (0, 0, W, 200), adet=7)
    _devre_izi(kd, rnd, (0, H - 200, W, H), adet=7)
    katman.putalpha(katman.getchannel("A").point(lambda a: int(a * 0.28)))
    tuval = Image.alpha_composite(tuval.convert("RGBA"), katman)

    # Logo zemine yedirilmiş filigran olarak giriyor — kart üstünde sert bir
    # rozet gibi durmasın diye (kullanıcı 28.08). Kadraj DIŞINA taşmıyor:
    # yarım kalan marka adı tasarım değil hata gibi okunuyor.
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((LOGO_BOY, LOGO_BOY), Image.LANCZOS)
    logo.putalpha(logo.getchannel("A").point(lambda a: int(a * 0.13)))
    tuval.alpha_composite(logo, (W - logo.width - 20, H - logo.height - 56))

    tuval = tuval.convert("RGB")
    return tuval, ImageDraw.Draw(tuval)


def _kirp_beyaz(foto: Image.Image, esik: int = 244) -> Image.Image:
    """Ürün fotoğrafının beyaz kenar boşluklarını kırpar.

    Pazaryeri fotoğrafları beyaz zeminde bol boşlukla geliyor; olduğu gibi
    yerleştirilince ürün kartın içinde küçücük kalıyor. Kırpınca ürün kartı
    dolduruyor ve akışta görünür oluyor.
    """
    gri = foto.convert("L")
    maske = gri.point(lambda p: 255 if p < esik else 0)
    kutu = maske.getbbox()
    if not kutu:
        return foto
    # Birkaç piksel pay bırak ki ürün kenarları kesilmesin
    pay = 8
    x0 = max(0, kutu[0] - pay)
    y0 = max(0, kutu[1] - pay)
    x1 = min(foto.width, kutu[2] + pay)
    y1 = min(foto.height, kutu[3] + pay)
    return foto.crop((x0, y0, x1, y1))


def _foto_kart(tuval: Image.Image, d: ImageDraw.ImageDraw, url: str) -> None:
    """Ürün fotoğrafını beyaz yuvarlak kartın içine oranını bozmadan yerleştirir."""
    x0, y0, x1, y1 = KART
    d.rounded_rectangle([x0, y0, x1, y1], radius=28, fill=BEYAZ,
                        outline=(226, 233, 239), width=2)

    # Uzak CDN'e bagimli olmamak icin defter fotograflari depoda duruyor
    # (28.08: cdn.dsmcdn.com zaman asimina ugrayinca tum uretim dusmustu).
    if url.startswith("http"):
        ham = _indir(url)
    else:
        ham = Image.open(CIKTI_DIZIN / url)
    foto = _kirp_beyaz(ham.convert("RGB"))
    ic_w, ic_h = (x1 - x0) - 56, (y1 - y0) - 56
    olcek = min(ic_w / foto.width, ic_h / foto.height)
    yeni = foto.resize((max(1, int(foto.width * olcek)), max(1, int(foto.height * olcek))),
                       Image.LANCZOS)
    px = x0 + ((x1 - x0) - yeni.width) // 2
    py = y0 + ((y1 - y0) - yeni.height) // 2
    tuval.paste(yeni, (px, py))


def _fiyat_rozeti(d: ImageDraw.ImageDraw, metin: str) -> None:
    """Fotoğraf kartının sağ üst köşesine oturan turuncu fiyat rozeti.

    Satış görselinde rakam görmeyen kullanıcı tıklamıyor, fiyatı merak edip
    kaydırıyor. Rozet fotoğrafın üstüne biniyor ki gözden kaçmasın.
    """
    f = _bold(34)
    gen = d.textlength(metin, font=f)
    ph, pw = 66, gen + 56
    x1, y0 = KART[2] - 18, KART[1] - 22
    x0 = x1 - pw
    d.rounded_rectangle([x0, y0, x1, y0 + ph], radius=ph / 2, fill=TURUNCU)
    d.text((x0 + 28, y0 + ph / 2 - 22), metin, font=f, fill=BEYAZ)


def uret(reklam: dict) -> pathlib.Path:
    tuval, d = _zemin_ac(f"ogretmen:{reklam['dosya']}")

    # Marka
    f = _mono(28)
    gen = _aralikli_genislik(d, MARKA, f, aralik=8)
    _aralikli(d, ((W - gen) / 2, 92), MARKA, f, TEAL, aralik=8)
    d.line([(W / 2 - 60, 66), (W / 2 + 60, 66)], fill=ALTIN, width=4)

    # Kitleyi eleyen şerit
    serit = reklam.get("serit", SERIT)
    fs = _mono(30)
    while _aralikli_genislik(d, serit, fs, aralik=8) > W - 60 and fs.size > 22:
        fs = _mono(fs.size - 2)
    gen = _aralikli_genislik(d, serit, fs, aralik=8)
    _aralikli(d, ((W - gen) / 2, 168), serit, fs, TURUNCU, aralik=8)

    _foto_kart(tuval, d, reklam["foto"])
    d = ImageDraw.Draw(tuval)

    # Fiyat rozeti — fotografin sag ust kosesine oturuyor
    _fiyat_rozeti(d, reklam["rozet_fiyat"])

    # Asıl vaat
    fb, satirlar, boyut = _sigdir(
        d, reklam["baslik"], W - 160, [([70, 62], 2), ([54], 3)]
    )
    y = 746
    for s in satirlar:
        d.text(((W - d.textlength(s, font=fb)) / 2, y), s, font=fb, fill=LACIVERT)
        y += int(boyut * 1.2)

    # Destek cümlesi — gerekirse küçülterek tek satırda tut. Blok taşacaksa
    # tamamen düşer: başlık iki satıra sığdığında (Arduino, endüstriyel) üç
    # fiyat kademesi + toptan satırı zaten CTA'ya kadar olan yeri dolduruyor.
    fd = _normal(28)
    while d.textlength(reklam["destek"], font=fd) > W - 140 and fd.size > 20:
        fd = _normal(fd.size - 2)
    kalan = len(reklam["fiyatlar"]) * 42 + (28 if reklam["toptan"] else 0)
    if y + 8 + fd.size + 16 + kalan <= METIN_TABANI:
        y += 8
        d.text(((W - d.textlength(reklam["destek"], font=fd)) / 2, y),
               reklam["destek"], font=fd, fill=GRI)
        y += fd.size + 16
    else:
        y += 14

    # Fiyat kademeleri ALT ALTA, adet ve tutar ayrı sütunda. Tek satırda
    # "Tekli 90 · 10'lu 850 · 20'li 1.700 TL" yazıyordu ve kullanıcı haklı
    # olarak "90 ne, 90 TL mi?" diye sordu — birimi bir kez sona koymak
    # okuyanı geri dönüp saymaya zorluyor.
    fe = _normal(30)
    ft = _bold(34)
    kademeler = reklam["fiyatlar"]
    eg = max(d.textlength(a, font=fe) for a, _ in kademeler)
    tg = max(d.textlength(b, font=ft) for _, b in kademeler)
    ara = 36
    x0 = (W - (eg + ara + tg)) / 2
    for etiket, tutar in kademeler:
        d.text((x0 + eg - d.textlength(etiket, font=fe), y + 4), etiket,
               font=fe, fill=GRI)
        d.text((x0 + eg + ara, y), tutar, font=ft, fill=LACIVERT)
        y += 42

    # Toptan satırı yalnız defter dışındaki ürünlerde: defterde kademeli
    # fiyat zaten yazılı, diğerlerinde adede göre özel fiyat konuşuluyor.
    if reklam["toptan"]:
        fto = _bold(26)
        d.text(((W - d.textlength(reklam["toptan"], font=fto)) / 2, y + 4),
               reklam["toptan"], font=fto, fill=TEAL)
        y += 2 + fto.size

    # Aciliyet — sezon penceresi dar, karari bugune cekiyor. CTA 1218'de
    # sabit (ust kenari 1172); metin tabani 1120'yi gecerse yerlesim tasar,
    # uretim sirasinda uyar ki sessizce bozuk gorsel cikmasin.
    fa = _mono(24)
    gen = _aralikli_genislik(d, ACELE, fa, aralik=5)
    if y + 22 > METIN_TABANI + 24:
        print(f"  UYARI: {reklam['dosya']} metin tabani {y:.0f}px — CTA'ya tasiyor")
    _aralikli(d, ((W - gen) / 2, min(max(y + 22, 1086), METIN_TABANI + 24)), ACELE, fa,
              TURUNCU, aralik=5)

    # CTA: alan adi degil EYLEM. Alan adi altta kucuk kaliyor.
    fp = _bold(40)
    gen = d.textlength(CTA, font=fp)
    ph, pw = 92, gen + 130
    x0, y0 = (W - pw) / 2, 1218 - ph / 2
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph / 2, fill=TURUNCU)
    d.text(((W - gen) / 2, 1218 - 27), CTA, font=fp, fill=BEYAZ)

    fs2 = _normal(28)
    d.text(((W - d.textlength(SITE, font=fs2)) / 2, 1288), SITE, font=fs2, fill=GRI)

    CIKTI_DIZIN.mkdir(parents=True, exist_ok=True)
    return _kaydet(tuval, CIKTI_DIZIN / reklam["dosya"])


def main() -> int:
    for r in REKLAMLAR:
        yol = uret(r)
        print(f"  uretildi: {yol.name}  ({yol.stat().st_size // 1024} KB)")
    print(f"\n{len(REKLAMLAR)} gorsel -> {CIKTI_DIZIN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
