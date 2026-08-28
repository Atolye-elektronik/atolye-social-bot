# -*- coding: utf-8 -*-
"""Meta reklamları için video üretir — yazı hiçbir zaman ürünün üstüne gelmez.

Neden yeniden kuruldu: elimizdeki kurgu videolarında yazılar doğrudan ürünün
üstünde duruyor ve ürünü kapatıyordu (kullanıcı 28.08). O yazılar videoya
gömülü olduğu için yerleri değiştirilemiyordu; bu yüzden reklam videoları ham
Kling kliplerinden yeniden kuruluyor.

Yerleşim sabit ve statik görsellerle aynı dili konuşuyor:

    üst    → marka + "MESLEKİ VE TEKNİK ANADOLU LİSELERİ İÇİN" şeridi
    orta   → klip kartı (940x980) — SADECE görüntü, hiç yazı yok
    alt    → başlık, fiyat kademeleri, aciliyet, CTA

Böylece ürün hiçbir karede kapanmıyor; okunacak her şey kendi şeridinde.

İki teknik ayrıntı:

  * **Kling filigranı** ham klibin sağ alt köşesinde. Üstünü kapatmak yerine
    klibin alt %7'si kırpılıyor — leke kalmıyor, kayıp da karenin en altındaki
    boşluktan gidiyor.
  * **Ses yok.** Pinterest bu müziklerden telif verdi; ücretli reklamda telifli
    müzik reddedilme ya da sessize alınma sebebi. Anlatım zaten alttaki yazı
    şeridinde, sessizde kaybolan bilgi yok.

    python tools/reklam_video.py
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw  # noqa: E402

from src.carousel_gorsel import (  # noqa: E402
    ALTIN, BEYAZ, TURUNCU,
    _aralikli, _aralikli_genislik, _bold, _mono, _normal, _sigdir,
)

KOK = pathlib.Path(__file__).resolve().parents[1]
KLIPLER = pathlib.Path.home() / "Desktop" / "kling-videolar"
CIKTI = KOK / "posts" / "media" / "meta-reklam"
FOTO_ONBELLEK = CIKTI / "kaynak"
LOGO = KOK / "posts" / "media" / "marka" / "logo.png"
LOGO_BOY = 130
CDN = "https://cdn.shopify.com/s/files/1/0801/9692/7717/files/"

W, H = 1080, 1920
# Kart iki taraftan da kisaldi. Reels/Hikaye'de Meta kendi arayuzunu
# videonun ustune bindiriyor: ust ~%14 (profil satiri) ve alt ~%20
# (aciklama + kendi siparis dugmesi). Kitleyi eleyen serit ustte, fiyat
# kademeleri altta o bantlarin DISINDA kalmali; kaybedilen kart
# yuksekligi bunun bedeli.
KART = (70, 340, 1010, 1100)          # klip kartı
KLIP_SN = 3.0                          # klip başına süre

ZEMIN = (245, 248, 250)
LACIVERT = (11, 20, 32)
TEAL = (13, 132, 124)
GRI = (104, 120, 136)

SERIT = "MESLEKİ VE TEKNİK ANADOLU LİSELERİ İÇİN"
MARKA = "ATÖLYE ELEKTRONİK"
SITE = "atolyeelektronik.com"
ACELE = "OKULLAR 14 EYLÜL'DE AÇILIYOR"
CTA = "Hemen Sipariş Ver"
TOPTAN = "Toplu alımda özel fiyat · bize yazın"

DEFTER_FIYAT = [("1 adet", "90 TL"), ("10 adet", "850 TL"),
                ("20 adet", "1.700 TL"), ("30 adet", "2.550 TL")]

REKLAMLAR = [
    {
        "dosya": "reklam-staj-defteri.mp4",
        # 3. sahne degisti: onceki klipte cildin kalinligi olduğundan
        # buyuk gorunuyordu (kullanici 28.08).
        "klipler": ["kling_20260819_VIDEO_Front_faci_5256_0.mp4",
                    "kling_20260823_is-dosyasi-pushin_4756.mp4",
                    "kling_20260823_is-dosyasi-orbit_4868.mp4"],
        "baslik": "Staj defteri, tek siparişte",
        "destek": "Tek fatura · tek kargo · aynı gün gönderim",
        "fiyatlar": DEFTER_FIYAT,
        "toptan": None,
    },
    {
        "dosya": "reklam-temrin-defteri.mp4",
        "klipler": ["kling_20260823_temrin-defteri-v2_4758.mp4",
                    "kling_20260823_temrin-spotlight_4868b.mp4"],
        "baslik": "Temrin defteri, tek siparişte",
        "destek": "48 yaprak 96 sayfa · aynı gün kargo",
        "fiyatlar": DEFTER_FIYAT,
        "toptan": None,
    },
    {
        "dosya": "reklam-takim-cantasi.mp4",
        # takimcantasisetibeyazdonus.mp4 denendi ama o baska bir organizer
        # kutusu, bizim SUPER-BAG cantamiz degil.
        "klipler": ["kling_20260819_VIDEO__4201_0.mp4",
                    "kling_20260625_VIDEO_I_ve_attac_101_0.mp4"],
        "baslik": "Atölye dersine hazır sınıf",
        "destek": "Pense, havya, multimetre, lehim takımı",
        "fiyatlar": [("17 parça tam set", "1.990 TL")],
        "toptan": TOPTAN,
    },
    {
        "dosya": "reklam-endustriyel.mp4",
        # Bu urune ait Kling klibi YOK. Elimizdeki "endustriyel-set-dolly"
        # aslinda breadboard/LED seti; yanlis urunu gostermektense urunun
        # kendi fotograflarindan yavas yaklasma yapiliyor (kullanici 28.08).
        "fotograflar": ["EndElkhepsi.webp?v=1782335968",
                        "entegretransistor.webp?v=1782335968",
                        "roleanahtar.webp?v=1782335969"],
        "baslik": "Endüstriyel Elektronik dersi, 11. sınıf",
        "destek": "Müfredattaki uygulamalar birebir, tek sette",
        "fiyatlar": [("Tam set", "699 TL")],
        "toptan": TOPTAN,
    },
    {
        "dosya": "reklam-arduino.mp4",
        # Uc Arduino setimizin kendi 3D videolari. Onceki secimde 2WD robot
        # kiti vardi; o ayri bir urun, bu reklamda isi yok (kullanici 28.08).
        "klipler": ["kling_20260823_arduino46-turntable_4667.mp4",
                    "kling_20260823_arduino56-dolly_4652.mp4",
                    "kling_20260823_arduino88-dolly_4781.mp4"],
        "baslik": "Mikrodenetleyiciler ve Robotik Kodlama",
        "destek": "Türkçe kaynak ve devre örnekleriyle",
        "fiyatlar": [("46 parça", "769 TL"), ("56 parça", "1.092 TL"),
                     ("88 parça", "1.766 TL")],
        "toptan": TOPTAN,
    },
]


def _foto_indir(ad: str) -> pathlib.Path:
    """Ürün fotoğrafını depoda tutar.

    Üretim uzak bir CDN'e bağlı olmamalı: 28.08'de bir CDN zaman aşımı tüm
    görsel üretimini düşürmüştü.
    """
    FOTO_ONBELLEK.mkdir(parents=True, exist_ok=True)
    hedef = FOTO_ONBELLEK / ad.split("?")[0]
    if not hedef.exists():
        import requests
        r = requests.get(CDN + ad, timeout=60)
        r.raise_for_status()
        hedef.write_bytes(r.content)
    return hedef


def _foto_kare(ad: str, kart_w: int, kart_h: int) -> pathlib.Path:
    """Fotoğrafı kart oranında beyaz zemine oturtur, iki katı çözünürlükte.

    Kenar payı bilerek geniş: yavaş yaklaşma %8 kırpıyor, pay olmasa ürünün
    kenarları kesiliyordu. İki kat çözünürlük yaklaşmada netliği koruyor.
    """
    ham = Image.open(_foto_indir(ad)).convert("RGB")
    tw, th = kart_w * 2, kart_h * 2
    olcek = min((tw - 200) / ham.width, (th - 200) / ham.height)
    yeni = ham.resize((max(1, int(ham.width * olcek)),
                       max(1, int(ham.height * olcek))), Image.LANCZOS)
    tuval = Image.new("RGB", (tw, th), BEYAZ)
    tuval.paste(yeni, ((tw - yeni.width) // 2, (th - yeni.height) // 2))
    yol = FOTO_ONBELLEK / f"_kare-{ad.split('?')[0]}.png"
    tuval.save(yol)
    return yol


def logo_katman(hedef: pathlib.Path) -> pathlib.Path:
    """Logoyu kartın sağ üst köşesine koyan saydam katman.

    Zemine değil videonun ÜSTÜNE biniyor: kartın içini klip kaplıyor, zemine
    çizilen logo görünmezdi.
    """
    kat = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((LOGO_BOY, LOGO_BOY), Image.LANCZOS)
    kat.alpha_composite(logo, (KART[2] - 26 - logo.width, KART[1] + 26))
    kat.save(hedef)
    return hedef


def _ffmpeg() -> str:
    yol = shutil.which("ffmpeg")
    if not yol:
        raise SystemExit("HATA: ffmpeg bulunamadi. Kurulu mu, PATH'te mi?")
    return yol


def zemin_uret(reklam: dict, hedef: pathlib.Path) -> pathlib.Path:
    """Klip kartının dışındaki her şeyi çizer; kartın içi videoya kalıyor."""
    tuval = Image.new("RGB", (W, H), ZEMIN)
    d = ImageDraw.Draw(tuval)

    # Marka
    f = _mono(28)
    gen = _aralikli_genislik(d, MARKA, f, aralik=8)
    _aralikli(d, ((W - gen) / 2, 200), MARKA, f, TEAL, aralik=8)
    d.line([(W / 2 - 60, 174), (W / 2 + 60, 174)], fill=ALTIN, width=4)

    # Kitleyi eleyen şerit
    fs = _mono(30)
    while _aralikli_genislik(d, SERIT, fs, aralik=8) > W - 60 and fs.size > 22:
        fs = _mono(fs.size - 2)
    gen = _aralikli_genislik(d, SERIT, fs, aralik=8)
    _aralikli(d, ((W - gen) / 2, 276), SERIT, fs, TURUNCU, aralik=8)

    # Klip kartı — video bunun üstüne biniyor, burada yalnız çerçevesi var
    d.rounded_rectangle(list(KART), radius=28, fill=BEYAZ,
                        outline=(226, 233, 239), width=2)

    # Başlık
    fb, satirlar, boyut = _sigdir(d, reklam["baslik"], W - 160,
                                  [([62, 56], 2), ([48], 3)])
    y = 1140
    for s in satirlar:
        d.text(((W - d.textlength(s, font=fb)) / 2, y), s, font=fb, fill=LACIVERT)
        y += int(boyut * 1.16)

    # Destek cümlesi
    fd = _normal(28)
    while d.textlength(reklam["destek"], font=fd) > W - 140 and fd.size > 20:
        fd = _normal(fd.size - 2)
    y += 6
    d.text(((W - d.textlength(reklam["destek"], font=fd)) / 2, y),
           reklam["destek"], font=fd, fill=GRI)
    y += fd.size + 16

    # Fiyat kademeleri: adet ve tutar ayrı sütunda, alt alta
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
        y += 44

    if reklam["toptan"]:
        fto = _bold(26)
        d.text(((W - d.textlength(reklam["toptan"], font=fto)) / 2, y + 4),
               reklam["toptan"], font=fto, fill=TEAL)
        y += 4 + fto.size

    # Aciliyet — Reels/Hikaye guvenli alaninin alt siniri ~1535px. Fiyat
    # kademeleri ve aciliyet bunun USTUNDE kalmali; CTA dugmesi ile site
    # adresi bilerek altta, onlar Feed'de gorunuyor, Reels'te zaten Meta
    # kendi siparis dugmesini koyuyor.
    GUVENLI_TABAN = 1535
    fa = _mono(24)
    gen = _aralikli_genislik(d, ACELE, fa, aralik=5)
    ya = y + 16
    if ya + fa.size > GUVENLI_TABAN:
        print(f"  UYARI: {reklam['dosya']} metin tabani {ya + fa.size:.0f}px — "
              f"Reels guvenli alanini asiyor")
    _aralikli(d, ((W - gen) / 2, min(ya, GUVENLI_TABAN - fa.size)), ACELE, fa,
              TURUNCU, aralik=5)

    # CTA
    fp = _bold(40)
    gen = d.textlength(CTA, font=fp)
    ph, pw = 92, gen + 130
    cx, cy = (W - pw) / 2, 1770 - ph / 2
    d.rounded_rectangle([cx, cy, cx + pw, cy + ph], radius=ph / 2, fill=TURUNCU)
    d.text(((W - gen) / 2, 1770 - 27), CTA, font=fp, fill=BEYAZ)

    fs2 = _normal(28)
    d.text(((W - d.textlength(SITE, font=fs2)) / 2, 1848), SITE, font=fs2, fill=GRI)

    tuval.save(hedef)
    return hedef


def uret(ffmpeg: str, reklam: dict) -> pathlib.Path:
    kart_w = KART[2] - KART[0]
    kart_h = KART[3] - KART[1]
    zemin = zemin_uret(reklam, CIKTI / "_zemin.png")

    fotograf_modu = "fotograflar" in reklam
    sahneler = reklam.get("fotograflar") or reklam["klipler"]

    girdiler: list[str] = ["-loop", "1", "-i", str(zemin)]
    for ad in sahneler:
        if fotograf_modu:
            girdiler += ["-loop", "1", "-t", str(KLIP_SN),
                         "-i", str(_foto_kare(ad, kart_w, kart_h))]
        else:
            yol = KLIPLER / ad
            if not yol.exists():
                raise SystemExit(f"HATA: klip yok -> {yol}")
            girdiler += ["-i", str(yol)]

    parcalar = []
    for i in range(len(sahneler)):
        if fotograf_modu:
            # Yavaş yaklaşma: duran fotoğraf akışta ölü duruyor, hafif
            # hareket bakışı tutuyor.
            #
            # zoompan KULLANILMIYOR: onun `d` parametresi HER girdi karesi
            # için o kadar kare üretiyor. -loop ile beslenen fotoğraf 90 kare
            # olduğu için ilk fotoğraf tüm videoyu dolduruyor, 2. ve 3. sahne
            # hiç görünmüyordu. Zamana bağlı ölçekleme aynı etkiyi verirken
            # süreyi girdinin kendi uzunluğu belirliyor.
            parcalar.append(
                f"[{i+1}:v]fps=30,"
                f"scale=w=\'{kart_w}*(1+0.14*t/{KLIP_SN})\':h=-2:eval=frame,"
                f"crop={kart_w}:{kart_h},setsar=1[c{i}]"
            )
        else:
            # Alt %7 kırpılıyor: Kling filigranı orada duruyor.
            #
            # Klip karta SIĞDIRILIYOR, doldurulmuyor. Önceden
            # force_original_aspect_ratio=increase + crop vardı; geniş ürün
            # çekimleri kare kartı doldururken kenarlardan kırpılıyor ve
            # malzemenin bir kısmı görünmüyordu (kullanıcı 28.08). Artan yer
            # klibin kendi bulanık kopyasıyla doluyor: beyaz zeminli çekimde
            # fark edilmiyor, koyu çekimde de bant gibi durmuyor.
            parcalar.append(
                f"[{i+1}:v]trim=0:{KLIP_SN},setpts=PTS-STARTPTS,"
                f"crop=iw:trunc(ih*0.93/2)*2:0:0,fps=30,split=2[b{i}][f{i}];"
                f"[b{i}]scale={kart_w}:{kart_h}:force_original_aspect_ratio=increase,"
                f"crop={kart_w}:{kart_h},gblur=sigma=28[bg{i}];"
                f"[f{i}]scale={kart_w}:{kart_h}:force_original_aspect_ratio=decrease[fg{i}];"
                f"[bg{i}][fg{i}]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2,"
                f"setsar=1[c{i}]"
            )
    zincir = "".join(f"[c{i}]" for i in range(len(sahneler)))
    parcalar.append(f"{zincir}concat=n={len(sahneler)}:v=1[kl]")
    logo_no = len(sahneler) + 1
    girdiler += ["-loop", "1", "-i", str(logo_katman(CIKTI / "_logo.png"))]
    parcalar.append(f"[0:v][kl]overlay={KART[0]}:{KART[1]}:shortest=1[kart]")
    parcalar.append(f"[kart][{logo_no}:v]overlay=0:0:shortest=1[v]")

    hedef = CIKTI / reklam["dosya"]
    subprocess.run(
        [ffmpeg, "-v", "error", "-y", *girdiler,
         "-filter_complex", ";".join(parcalar),
         "-map", "[v]", "-an",
         "-t", str(KLIP_SN * len(sahneler)),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(hedef)],
        check=True)
    zemin.unlink()
    (CIKTI / "_logo.png").unlink(missing_ok=True)
    return hedef


def main() -> int:
    ffmpeg = _ffmpeg()
    CIKTI.mkdir(parents=True, exist_ok=True)
    for r in REKLAMLAR:
        yol = uret(ffmpeg, r)
        sn = KLIP_SN * len(r.get("fotograflar") or r["klipler"])
        print(f"  uretildi: {yol.name}  ({yol.stat().st_size // 1024} KB, {sn:.0f} sn)")
    print(f"\n{len(REKLAMLAR)} reklam videosu -> {CIKTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
