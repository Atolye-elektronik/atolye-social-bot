"""Ürün görsellerinden TikTok/Reels için dikey (1080x1920) video üretir.

Carousel slide'larıyla aynı marka dili kullanılır (koyu lacivert zemin,
turkuaz devre izleri, turuncu vurgu) — sadece dikey ve hareketli. Her kare
ffmpeg'in `zoompan` filtresiyle yavaşça yakınlaşır, böylece TikTok'un
sevmediği "donuk slayt" hissi olmaz.

    python -m src.video_uretim --post 2026-08-20-senaryo-arduino-baslangic-seti
    python -m src.video_uretim --gorsel a.jpg b.jpg --cikti posts/media/tanitim.mp4

Gereksinim: ffmpeg. GitHub Actions'ın ubuntu imajında hazır geliyor;
GitLab'ın python:3.12-slim imajına `apt-get install ffmpeg` gerekiyor
(.gitlab-ci.yml içindeki iş bunu zaten yapıyor).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import random
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

from . import posts
from .carousel_gorsel import (
    ALTIN,
    BEYAZ,
    GRI,
    SITE,
    TURKUAZ,
    TURUNCU,
    ZEMIN,
    _ac,
    _bold,
    _devre_izi,
    _mono,
    _normal,
    _sar,
    _sigdir,
)

W, H = 1080, 1920          # TikTok / Reels / Shorts 9:16
FPS = 30
KARE_SURESI = 3.0          # rolü bilinmeyen görsel kaç saniye kalsın
MAKS_SURE = 60.0           # toplam süre tavanı

# Carousel'de tempoyu izleyici belirliyor — istediği slide'da duruyor. Videoda
# tempoyu biz belirliyoruz, o yüzden her kare kendi işine göre süre alıyor:
# metin ağırlıklı hikaye kareleri okunacak kadar durur, ürün fotoğrafları
# oyalanmaz. Eşleşme dosya adından yapılıyor (01-kanca.jpg, 05-urun.jpg ...).
SLIDE_SURELERI = {
    "kanca": 2.8,
    "dert": 3.6,
    "hayal": 3.6,
    "cozum": 3.0,
    "kapak": 2.4,
    "urun": 1.9,
    "kapanis": 2.8,
}

# İlk saniyeler her şeyi belirlediği için kanca karesi ayrı tutuluyor.
# 26.08: 2.6 sn cok uzundu, izleyici kanca karesinde kaciyordu.
KANCA_SURESI = 1.8

# Arka plan müziği. Buraya .mp3/.m4a koyarsan video üretimi kendiliğinden
# birini seçer; klasör boşsa video sessiz kalır (hata vermez).
MUZIK_DIR = pathlib.Path("content/muzik")
MUZIK_SES_DUZEYI = float(os.environ.get("VIDEO_MUZIK_SES", "0.75"))


def muzik_sec(slug: str = "") -> pathlib.Path | None:
    """content/muzik içinden bir parça seçer.

    Seçim slug'a göre sabit: aynı post her üretimde aynı müziği alır, ama
    farklı postlar farklı parça kullanır — hepsinde aynı melodi olmasın.
    """
    if not MUZIK_DIR.exists():
        return None
    parcalar = sorted(
        p for p in MUZIK_DIR.iterdir()
        if p.suffix.lower() in (".mp3", ".m4a", ".aac", ".wav")
    )
    if not parcalar:
        return None
    if not slug:
        return parcalar[0]
    return parcalar[sum(ord(h) for h in slug) % len(parcalar)]

# Kanca karesinin üstündeki küçük etiket. Hepsinde aynısını kullanmak, arka
# arkaya birkaç videoyu gören izleyiciye tekrar hissi veriyor. Etiket cümlenin
# tipine göre seçiliyor — rastgele seçim "İTİRAF ET" etiketini bir temenni
# cümlesinin üstüne koyabiliyordu.
KANCA_ETIKETLERI = {
    # "... olsaydı?" — temenni
    "temenni": ("PEKİ YA ŞÖYLE OLSA?", "BİR DÜŞÜN"),
    # soru cümlesi — havuz geniş tutuldu, yoksa arka arkaya iki postta
    # aynı etiket çıkabiliyor
    "soru": ("TANIDIK GELDİ Mİ?", "HIZLI SORU", "İTİRAF ET", "BU SENSİN", "DUR BİR"),
    # düz cümle / iddia
    "cumle": ("DURUM ŞU", "SANA SÖYLÜYORUM", "BİR SANİYE", "ŞUNU BİL"),
}


def _kanca_etiketi(metin: str) -> str:
    """Kanca cümlesinin tipine göre etiket seçer (aynı metin hep aynı etiket)."""
    duz = metin.strip().lower()
    if duz.endswith("?"):
        tip = "temenni" if ("olsa?" in duz or "olsaydı?" in duz) else "soru"
    else:
        tip = "cumle"
    havuz = KANCA_ETIKETLERI[tip]
    return havuz[sum(ord(h) for h in metin) % len(havuz)]


class VideoHatasi(RuntimeError):
    pass


def _ffmpeg() -> str:
    yol = shutil.which("ffmpeg")
    if not yol:
        raise VideoHatasi(
            "ffmpeg bulunamadı. Windows'ta: winget install Gyan.FFmpeg — "
            "Debian/Ubuntu'da: apt-get install ffmpeg"
        )
    return yol


def _calistir(komut: list[str]) -> None:
    sonuc = subprocess.run(komut, capture_output=True, text=True)
    if sonuc.returncode != 0:
        kuyruk = (sonuc.stderr or "").strip().splitlines()[-8:]
        raise VideoHatasi("ffmpeg hatası:\n  " + "\n  ".join(kuyruk))


# --- Kare çizimi -------------------------------------------------------------


def _dikey_zemin(seed: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    tuval = Image.new("RGB", (W, H), ZEMIN)
    d = ImageDraw.Draw(tuval)
    rnd = random.Random(seed)
    # Dekor kenarlarda kalsın, ortadaki ürün alanı temiz görünsün.
    _devre_izi(d, rnd, (0, 0, W, 260), adet=9)
    _devre_izi(d, rnd, (0, H - 300, W, H), adet=9)
    _devre_izi(d, rnd, (0, 300, 120, H - 320), adet=5)
    _devre_izi(d, rnd, (W - 120, 300, W, H - 320), adet=5)
    return tuval, d


def _slide_suresi(kaynak, varsayilan: float) -> float:
    """Dosya adındaki role göre kareye süre verir."""
    ad = pathlib.Path(str(kaynak)).stem.lower()
    for rol, sure in SLIDE_SURELERI.items():
        if rol in ad:
            return sure
    return varsayilan


def kanca_kare(
    metin: str,
    cikti: pathlib.Path,
    etiket: str | None = None,
    arka_plan=None,
    kart: bool = True,
) -> pathlib.Path:
    """Videonun ilk karesi: izleyiciyi durduran soru/iddia.

    26.08 TikTok analizi: bu kare eskiden ürünsüz, düz zemin üzerine yazıdan
    ibaretti ve 2.6 saniye ekranda kalıyordu. Sonuç: izleyicilerin çoğu daha
    1. saniyede kaydırıp geçiyordu (ort. izlenme 1.4-2.1 sn, tamamlanma %0)
    ve videolar 2-0 izlenmede kaldı. Artık kanca cümlesi ürün fotoğrafının
    üstüne biniyor — ilk karede hem merak hem "bu ne ürünü" cevabı var.
    """
    tuval, d = _dikey_zemin(f"kanca:{metin}")
    etiket = etiket or _kanca_etiketi(metin)

    # Ürün fotoğrafı varsa kare ikiye bölünür: üstte kanca cümlesi, altta
    # ürün. Fotoğrafı tam ekran arkaya yaymak denendi ama ürünün kendi
    # üstündeki yazılar kanca cümlesiyle çakışıyordu — kart içinde duruyor.
    urun_karti = None
    if arka_plan is not None:
        try:
            urun_karti = _ac(arka_plan)
        except Exception:
            urun_karti = None  # açılamazsa kare yine üretilsin

    # Metin alanı kenar dekorunun (soldan/sağdan 120 px) içine girmesin.
    metin_genisligi = W - 300

    etiket_y = 300 if urun_karti is not None else 540
    f_etiket = _bold(46)
    gen = d.textlength(etiket, font=f_etiket)
    d.text(((W - gen) / 2, etiket_y), etiket, font=f_etiket, fill=TURUNCU)

    # Kanca cümlesinin uzunluğu değişken; kırpmak yerine sığana kadar küçült.
    f_metin, satirlar, boyut = _sigdir(
        d,
        metin,
        metin_genisligi,
        [([88, 80], 3), ([72, 64], 4), ([58, 52], 5)],
    )

    satir_yuksekligi = boyut + 20
    if urun_karti is not None:
        y = etiket_y + 130
    else:
        y = (H - len(satirlar) * satir_yuksekligi) / 2 - 60
    for satir in satirlar:
        gen = d.textlength(satir, font=f_metin)
        d.text(((W - gen) / 2, y), satir, font=f_metin, fill=BEYAZ)
        y += satir_yuksekligi

    d.line([(W / 2 - 90, y + 60), (W / 2 + 90, y + 60)], fill=TURKUAZ, width=6)

    if urun_karti is not None:
        # Ürün, yazının altında — kadranın alt yarısı.
        kart_boy = 780
        kart_x = (W - kart_boy) // 2
        kart_y = min(int(y + 150), H - kart_boy - 120)
        if kart:
            # Çıplak ürün fotoğrafı: beyaz kart içinde dursun.
            d.rounded_rectangle(
                [kart_x, kart_y, kart_x + kart_boy, kart_y + kart_boy],
                radius=48,
                fill=(255, 255, 255),
            )
            urun_karti.thumbnail((kart_boy - 70, kart_boy - 70), Image.LANCZOS)
            yapistir_x = kart_x + (kart_boy - urun_karti.width) // 2
            yapistir_y = kart_y + (kart_boy - urun_karti.height) // 2
        else:
            # Kaynak zaten tasarlanmış bir slide; beyaz kart eklemek "kart
            # içinde kart" görüntüsü yaratıyor — olduğu gibi, büyükçe koy.
            urun_karti.thumbnail((kart_boy + 120, kart_boy + 60), Image.LANCZOS)
            yapistir_x = (W - urun_karti.width) // 2
            yapistir_y = min(int(y + 130), H - urun_karti.height - 90)
        tuval.paste(urun_karti, (yapistir_x, yapistir_y))
    else:
        f_alt = _normal(40)
        alt = "izlemeye devam et"
        gen = d.textlength(alt, font=f_alt)
        d.text(((W - gen) / 2, y + 110), alt, font=f_alt, fill=GRI)

    cikti.parent.mkdir(parents=True, exist_ok=True)
    tuval.save(cikti, "PNG")
    return cikti


def kare_sade(kaynak, cikti: pathlib.Path) -> pathlib.Path:
    """Görseli olduğu gibi, marka zeminine ortalayarak kullanır.

    Kaynak zaten tasarlanmış bir slide ise (`posts/media/carousel/` altındakiler
    gibi) marka çerçevesini tekrar çizmek kart içinde kart görüntüsü yaratıyor.

    Kırpmak yerine sığdırıyoruz: carousel slide'ları 4:5, dikey kadraj 9:16 —
    kırpma yapılsa slide'ın sağı solu, dolayısıyla başlık metni kesiliyor.
    Artan üst/alt boşluk slide'ın kendi zemin rengiyle dolduğu için dikiş
    görünmüyor.
    """
    foto = _ac(kaynak)
    olcek = min(W / foto.width, H / foto.height)
    foto = foto.resize((round(foto.width * olcek), round(foto.height * olcek)), Image.LANCZOS)

    tuval = Image.new("RGB", (W, H), ZEMIN)
    tuval.paste(foto, ((W - foto.width) // 2, (H - foto.height) // 2))

    cikti.parent.mkdir(parents=True, exist_ok=True)
    tuval.save(cikti, "PNG")
    return cikti


def kare(
    kaynak,
    baslik: str,
    cikti: pathlib.Path,
    alt_yazi: str = "",
    sira: tuple[int, int] | None = None,
) -> pathlib.Path:
    """Tek bir video karesi çizer (1080x1920 PNG)."""
    tuval, d = _dikey_zemin(f"{baslik}:{cikti.name}")

    # Marka şeridi
    f_marka = _mono(30)
    marka = "ATÖLYE ELEKTRONİK"
    gen = d.textlength(marka, font=f_marka)
    d.text(((W - gen) / 2, 120), marka, font=f_marka, fill=TURKUAZ)
    d.line([(W / 2 - 70, 100), (W / 2 + 70, 100)], fill=ALTIN, width=4)

    # Ürün fotoğrafı — beyaz kart içinde, kareye sığdırılmış
    kart_x, kart_y, kart_boy = 90, 470, 900
    d.rounded_rectangle(
        [kart_x, kart_y, kart_x + kart_boy, kart_y + kart_boy],
        radius=48,
        fill=(255, 255, 255),
    )
    foto = _ac(kaynak)
    foto.thumbnail((kart_boy - 70, kart_boy - 70), Image.LANCZOS)
    tuval.paste(
        foto,
        (
            kart_x + (kart_boy - foto.width) // 2,
            kart_y + (kart_boy - foto.height) // 2,
        ),
    )

    # Başlık — kartın altında, en fazla üç satır
    f_baslik = _bold(64)
    satirlar = _sar(d, baslik.upper(), f_baslik, W - 160, maxsatir=3)
    y = kart_y + kart_boy + 90
    for satir in satirlar:
        gen = d.textlength(satir, font=f_baslik)
        d.text(((W - gen) / 2, y), satir, font=f_baslik, fill=BEYAZ)
        y += 78

    if alt_yazi:
        f_alt = _normal(38)
        for satir in _sar(d, alt_yazi, f_alt, W - 200, maxsatir=2):
            gen = d.textlength(satir, font=f_alt)
            d.text(((W - gen) / 2, y + 20), satir, font=f_alt, fill=GRI)
            y += 52

    # Sayaç (2/7 gibi)
    if sira:
        f_sayac = _mono(30)
        metin = f"{sira[0]}/{sira[1]}"
        gen = d.textlength(metin, font=f_sayac)
        d.text((W - gen - 70, 120), metin, font=f_sayac, fill=GRI)

    # Alt CTA
    f_cta = _bold(42)
    gen = d.textlength(SITE, font=f_cta)
    pw, ph = gen + 120, 88
    x0 = (W - pw) / 2
    y0 = H - 210
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph / 2, fill=TURUNCU)
    d.text(((W - gen) / 2, y0 + 20), SITE, font=f_cta, fill=BEYAZ)

    cikti.parent.mkdir(parents=True, exist_ok=True)
    tuval.save(cikti, "PNG")
    return cikti


# --- Video birleştirme -------------------------------------------------------


def _segment(png: pathlib.Path, hedef: pathlib.Path, sure: float) -> None:
    """Tek kareyi yavaşça yakınlaşan bir video parçasına çevirir."""
    kare_sayisi = max(1, int(sure * FPS))
    zoom = (
        f"zoompan=z='min(zoom+0.0007,1.12)'"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={kare_sayisi}:s={W}x{H}:fps={FPS},format=yuv420p"
    )
    _calistir(
        [
            _ffmpeg(), "-y", "-loglevel", "error",
            "-loop", "1", "-i", str(png),
            "-t", f"{sure:.2f}",
            "-vf", zoom,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-r", str(FPS), "-pix_fmt", "yuv420p",
            str(hedef),
        ]
    )


def birlestir(
    segmentler: list[pathlib.Path],
    cikti: pathlib.Path,
    muzik: pathlib.Path | None = None,
    toplam_sure: float | None = None,
) -> pathlib.Path:
    # Liste dosyası segmentlerin yanında dursun; çıktı klasörü (posts/media)
    # ffmpeg yarıda kalırsa artık dosyayla kirlenmesin.
    liste = segmentler[0].parent / "_segmentler.txt"
    liste.write_text(
        "\n".join(f"file '{s.as_posix()}'" for s in segmentler) + "\n",
        encoding="utf-8",
    )

    komut = [
        _ffmpeg(), "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(liste),
    ]
    if muzik and muzik.exists():
        # Müzik konuşmayı bastırmasın diye kısılıyor; sonda da yumuşak biterek
        # aniden kesilmiyor.
        ses = [f"volume={MUZIK_SES_DUZEYI}"]
        if toplam_sure and toplam_sure > 2.5:
            ses.append(f"afade=t=out:st={toplam_sure - 2:.2f}:d=2")
        komut += [
            "-i", str(muzik),
            "-map", "0:v", "-map", "1:a",
            "-af", ",".join(ses),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-shortest",
        ]
        print(f"  🎵 müzik: {muzik.name} (ses {MUZIK_SES_DUZEYI})")
    else:
        komut += ["-c", "copy"]
    komut.append(str(cikti))

    _calistir(komut)
    liste.unlink(missing_ok=True)
    return cikti


def uret(
    gorseller: list,
    cikti: pathlib.Path,
    basliklar: list[str] | None = None,
    sure: float = KARE_SURESI,
    muzik: pathlib.Path | None = None,
    sade: bool = False,
    kanca: str | None = None,
    kanca_etiket: str | None = None,
) -> pathlib.Path:
    """Görsel listesinden dikey video üretir.

    `sade=True` marka çerçevesi çizmez — kaynak zaten tasarlanmış slide'sa
    (carousel çıktıları) bunu kullan.

    `kanca` verilirse videonun başına, izleyiciyi durduracak bir açılış karesi
    eklenir. Görseller arasında zaten bir kanca slide'ı varsa (senaryo
    carousel'leri) bunu vermeye gerek yok.
    """
    if not gorseller:
        raise VideoHatasi("Video için en az bir görsel gerekiyor.")

    # Eksik dosyayı ffmpeg'e kadar taşımak ham bir traceback üretiyordu;
    # hangi dosyanın eksik olduğunu baştan söyleyelim.
    eksik = [
        str(g)
        for g in gorseller
        if not str(g).startswith(("http://", "https://")) and not pathlib.Path(g).exists()
    ]
    if eksik:
        raise VideoHatasi(
            "Şu görseller bulunamadı:\n  " + "\n  ".join(eksik)
            + "\nPostun media alanındaki yolları kontrol et."
        )

    basliklar = basliklar or []
    cikti = pathlib.Path(cikti)
    cikti.parent.mkdir(parents=True, exist_ok=True)

    # Her kare rolüne göre süre alır; toplam tavanı aşarsa hepsi aynı oranda
    # kısalır, böylece karelerin birbirine göre dengesi korunur.
    sureler = [_slide_suresi(g, sure) for g in gorseller]
    if kanca:
        sureler.insert(0, KANCA_SURESI)
    toplam = sum(sureler)
    if toplam > MAKS_SURE:
        sureler = [s * MAKS_SURE / toplam for s in sureler]
        toplam = MAKS_SURE

    with tempfile.TemporaryDirectory(prefix="atolye-video-") as gecici:
        gecici_yol = pathlib.Path(gecici)
        segmentler: list[pathlib.Path] = []
        kareler: list[pathlib.Path] = []

        if kanca:
            # Kanca karesinde gösterilecek görsel: ilk slayt çoğu zaman kapak
            # (yazı kartı) oluyor — kartın içine yazı koymak anlamsız. Adında
            # "urun" geçen ilk slaydı tercih et, yoksa ilk slayda düş.
            kanca_gorseli = next(
                (
                    g
                    for g in gorseller
                    if "urun" in pathlib.Path(str(g)).stem.lower()
                ),
                gorseller[0],
            )
            kareler.append(
                kanca_kare(
                    kanca,
                    gecici_yol / "kare-00.png",
                    kanca_etiket,
                    arka_plan=kanca_gorseli,
                    kart=not sade,
                )
            )

        for i, gorsel in enumerate(gorseller, start=1):
            hedef_png = gecici_yol / f"kare-{i:02d}.png"
            if sade:
                kareler.append(kare_sade(gorsel, hedef_png))
            else:
                baslik = (
                    basliklar[i - 1]
                    if i <= len(basliklar)
                    else (basliklar[0] if basliklar else "")
                )
                kareler.append(
                    kare(
                        gorsel,
                        baslik,
                        hedef_png,
                        sira=(i, len(gorseller)) if len(gorseller) > 1 else None,
                    )
                )

        for i, (png, kare_suresi) in enumerate(zip(kareler, sureler), start=1):
            segment = gecici_yol / f"seg-{i:02d}.mp4"
            _segment(png, segment, kare_suresi)
            segmentler.append(segment)
            print(f"  🎞️  kare {i}/{len(kareler)} ({kare_suresi:.1f} sn)")

        birlestir(segmentler, cikti, muzik, toplam)

    boyut = cikti.stat().st_size // 1024
    print(f"✅ video hazır: {cikti} ({boyut} KB, ~{toplam:.0f} sn)")
    return cikti


# --- Slaytları video diline çevirme ------------------------------------------


def _senaryoyu_bul(caption: str):
    """Postun metninden hangi senaryodan üretildiğini bulur.

    Senaryonun kanca cümlesi postun ilk satırı oluyor. Eşleştirmeyi
    senaryo_source yapıyor: her senaryonun bir `kanca_caption`'ı ve ürüne göre
    seçilen alternatifleri var, ilk satır bunlardan herhangi biri olabiliyor.
    """
    from . import senaryo_source

    ilk = next((s.strip() for s in caption.splitlines() if s.strip()), "")
    return senaryo_source.senaryo_bul(ilk)


def _urun_adi(caption: str) -> str:
    """Post metninden ürün adını çıkarır.

    Senaryolu postlarda ad '⚡ Ürün Adı: açıklama' satırında, klasik
    carousel'lerde ise ilk satırda ('📸 Ürün Adı') duruyor.
    """
    for satir in caption.splitlines():
        satir = satir.strip()
        if satir.startswith("⚡") and ":" in satir:
            return satir.lstrip("⚡ ").split(":", 1)[0].strip()

    ilk = next((s.strip() for s in caption.splitlines() if s.strip()), "")
    return ilk.lstrip("📸 ").strip()


def video_slaytlari(gorseller: list[str], caption: str, hedef_klasor: pathlib.Path) -> list[str]:
    """Metin slaytlarını video diliyle yeniden üretir.

    Carousel slaytlarının altında "devamı var" / "Detaylar fotoğraflarda"
    yazıyor; videoda kaydırılacak fotoğraf yok. Bu yüzden metin slaytları
    (kanca, dert, hayal, çözüm) carousel_gorsel'in video biçimiyle
    (bicim="video") yeniden çiziliyor. Ürün fotoğrafı içeren slaytlarda böyle
    bir ifade geçmediği için onlara dokunulmuyor — Shopify'a gitmeye de gerek
    kalmıyor.
    """
    senaryo = _senaryoyu_bul(caption)

    from . import carousel_gorsel

    hedef_klasor.mkdir(parents=True, exist_ok=True)
    yeni: list[str] = []
    for yol in gorseller:
        ad = pathlib.Path(yol).stem.lower()
        cikti = hedef_klasor / pathlib.Path(yol).name

        if senaryo and any(k in ad for k in ("kanca", "dert", "hayal")):
            anahtar = next(k for k in ("kanca", "dert", "hayal") if k in ad)
            spec = senaryo[anahtar]
            carousel_gorsel.metin(
                spec["etiket"], spec["baslik"], spec["metin"], cikti,
                bicim="video",
            )
            yeni.append(str(cikti))
        elif "cozum" in ad or "kapak" in ad:
            # Çözüm (senaryolu) ve kapak (klasik) slaytları aynı çiziciden
            # geliyor ve ikisinde de "Detaylar fotoğraflarda" yazıyor.
            carousel_gorsel.kapak(
                _urun_adi(caption) or "Atölye Elektronik",
                cikti,
                alt_baslik=(
                    senaryo["cozum_etiket"] if senaryo else "ÜRÜN TANITIMI"
                ),
                bicim="video",
            )
            yeni.append(str(cikti))
        else:
            # Ürün ve kapanış slaytlarında devam ipucu yok.
            yeni.append(yol)
    return yeni


# --- CLI ---------------------------------------------------------------------


def _posttan(
    slug: str,
    cikti: pathlib.Path | None,
    sure: float,
    muzik,
    sade: bool,
    kanca: str | None,
    kanca_etiket: str | None,
    oneri: bool = True,
    sessiz: bool = False,
) -> int:
    hedef = next((p for p in posts.load_all() if p.slug == slug), None)
    if hedef is None:
        print(f"Post bulunamadı: {slug}")
        return 1

    gorseller = [g for g in hedef.media_list if not g.lower().endswith((".mp4", ".mov"))]
    if not gorseller:
        print(f"{slug} postunda görsel yok.")
        return 1

    # Carousel slide'ları zaten marka çerçevesiyle üretilmiş; üstüne bir kez
    # daha çerçeve çizmek kart içinde kart görüntüsü yaratıyor.
    if not sade and all("carousel" in g.replace("\\", "/").lower() for g in gorseller):
        sade = True
        print("ℹ️  Görseller hazır carousel slide'ları — sade mod kullanılıyor.")

    # Senaryo carousel'leri kancayla açılıyor (01-kanca.jpg); klasik olanlar
    # düz kapakla. Kancası olmayan videoya kanca üretmek yerine uyarıyoruz —
    # ürün adını kanca diye göstermek izleyiciyi durdurmaz.
    kanca = kanca or hedef.extra.get("tiktok_kanca")
    kanca_slaydi_var = any("kanca" in g.lower() for g in gorseller)
    if kanca_slaydi_var:
        if kanca:
            print("ℹ️  Görsellerde zaten kanca slide'ı var — verilen kanca metni kullanılmadı.")
        kanca = None
    elif not kanca:
        print(
            "⚠️  Bu videonun kancası yok — ilk kare düz kapak. TikTok'ta ilk saniye\n"
            "    kaydırılmayı belirliyor. Postun front matter'ına şöyle bir satır ekle:\n"
            "      tiktok_kanca: Elektroniğe başlamak istiyorsun ama nereden?\n"
            "    ya da komuta --kanca \"...\" ver."
        )

    # Carousel slaytlarındaki "devamı var" / "Detaylar fotoğraflarda" ifadeleri
    # videoda anlamsız; metin slaytlarını video diliyle yeniden üret.
    if sade:
        oncesi = list(gorseller)
        gorseller = video_slaytlari(
            gorseller, hedef.caption, pathlib.Path(f"posts/media/video-slayt/{slug}")
        )
        degisen = sum(1 for a, b in zip(oncesi, gorseller) if a != b)
        if degisen:
            print(f"ℹ️  {degisen} metin slaydı video diliyle yeniden üretildi")

    # Müzik verilmediyse content/muzik içinden seç.
    if sessiz:
        print("🔇 sessiz üretim — sesi platformda yükleme sonrası seçeceksin")
    elif muzik is None:
        muzik = muzik_sec(slug)
        if muzik is None:
            print(
                f"ℹ️  Video sessiz olacak — {MUZIK_DIR}/ klasörüne .mp3 koyarsan\n"
                "    otomatik olarak arka plan müziği eklenir."
            )

    basliklar = [ln.strip() for ln in hedef.caption.splitlines() if ln.strip()]
    cikti = cikti or pathlib.Path(f"posts/media/{slug}.mp4")
    uret(
        gorseller,
        cikti,
        basliklar,
        sure,
        muzik,
        sade,
        kanca,
        kanca_etiket or hedef.extra.get("tiktok_kanca_etiket"),
    )

    # Otomasyon içinden çağrıldığında bu öneri gereksiz gürültü.
    if not oneri:
        return 0

    # Biçim posts.parse_datetime'in kabul ettiği biçim olmalı; datetime'ı
    # olduğu gibi basmak "2026-08-20 19:10:00+03:00" üretiyor ve o ayrıştırılamıyor.
    zaman = hedef.publish_at.strftime("%Y-%m-%d %H:%M") if hedef.publish_at else "YYYY-MM-DD HH:MM"

    print("\nPostun front matter'ına şunları ekleyip TikTok'a gönderebilirsin:")
    print(f"  media: {cikti.as_posix()}")
    print("  platforms: [tiktok_studio]")
    print(f"  tiktok_schedule_at: {zaman}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Görsellerden dikey video üretir")
    parser.add_argument("--post", help="Post dosya adı (.md olmadan)")
    parser.add_argument("--gorsel", nargs="+", help="Görsel yolları ya da URL'leri")
    parser.add_argument("--baslik", nargs="*", default=None, help="Kare başlıkları")
    parser.add_argument("--cikti", type=pathlib.Path, help="Çıktı mp4 yolu")
    parser.add_argument("--sure", type=float, default=KARE_SURESI, help="Kare başına saniye")
    parser.add_argument("--muzik", type=pathlib.Path, help="Arka plan müziği (mp3)")
    parser.add_argument(
        "--sade",
        action="store_true",
        help="Marka çerçevesi çizme — kaynak zaten tasarlanmış slide ise kullan",
    )
    parser.add_argument(
        "--kanca",
        help="Videonun başına eklenecek açılış cümlesi (izleyiciyi durduran soru/iddia)",
    )
    parser.add_argument(
        "--kanca-etiket",
        dest="kanca_etiket",
        help="Kanca karesindeki küçük üst etiket (verilmezse cümle tipine göre seçilir)",
    )
    parser.add_argument(
        "--oneri-yok",
        dest="oneri",
        action="store_false",
        help="Sonda front matter önerisi yazma (otomasyon içinden çağrılırken)",
    )
    parser.add_argument(
        "--sessiz",
        action="store_true",
        help="content/muzik dolu olsa bile müzik ekleme — sesi platformda "
             "yükleme sonrası seçeceksen bunu kullan",
    )
    args = parser.parse_args(argv)

    try:
        if args.post:
            return _posttan(
                args.post,
                args.cikti,
                args.sure,
                args.muzik,
                args.sade,
                args.kanca,
                args.kanca_etiket,
                args.oneri,
                args.sessiz,
            )
        if args.gorsel:
            cikti = args.cikti or pathlib.Path("posts/media/video.mp4")
            uret(
                args.gorsel,
                cikti,
                args.baslik,
                args.sure,
                None if args.sessiz else args.muzik,
                args.sade,
                args.kanca,
                args.kanca_etiket,
            )
            return 0
    except VideoHatasi as exc:
        print(f"❌ {exc}")
        return 1

    parser.error("--post ya da --gorsel vermelisin")
    return 2


if __name__ == "__main__":
    sys.exit(main())
