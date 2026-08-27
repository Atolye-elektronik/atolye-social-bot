# -*- coding: utf-8 -*-
"""Meta reklamları için öğretmene yönelik görseller üretir.

Neden ayrı bir araç: elimizdeki 53 video ve carousel slaytı ÖĞRENCİYE
sesleniyor — ürünü anlatıyor. Öğretmen mesajı bambaşka: ürünü değil **çözümü**
anlatır ("tüm sınıf, tek sipariş, tek fatura"). Facebook'ta metin okunduğu ve
öğretmen kitlesi orada ağırlıklı olduğu için video yerine net tek görsel
tercih edildi.

Kitleyi görselin kendisi eliyor: en üstteki şerit doğrudan "MESLEK LİSESİ
ÖĞRETMENLERİNE" diyor. Meta'da artık meslek hedeflemesi olmadığı için
(bkz. meta-ads-kurulum.md) eleme işini yaratıcı yapıyor.

Stil src/carousel_gorsel.py'den geliyor; marka görünümü carousel'lerle birebir
aynı kalsın diye oradaki ilkeller yeniden kullanılıyor.

    python tools/meta_ogretmen_gorsel.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.carousel_gorsel import (  # noqa: E402
    ALTIN, BEYAZ, GRI, TURKUAZ, TURUNCU, W,
    _aralikli, _aralikli_genislik, _bold, _kaydet, _marka_baslik, _mono,
    _normal, _pill, _sigdir, _zemin,
)

SERIT = "MESLEK LİSESİ ÖĞRETMENLERİNE"

REKLAMLAR = [
    {
        "dosya": "meta-ogretmen-defter.png",
        "baslik": "Sınıfın tamamı, tek sipariş",
        "maddeler": [
            "10, 20 ve 30'lu sınıf paketleri",
            "Tek fatura, tek kargo",
            "MEB müfredatına ve staj yönetmeliğine uygun",
        ],
        "rozet": "STAJ VE TEMRİN DEFTERİ",
    },
    {
        "dosya": "meta-ogretmen-takim-cantasi.png",
        "baslik": "Atölye dersine hazır sınıf",
        "maddeler": [
            "17 parça: pense, havya, multimetre, lehim takımı",
            "Sınıf adedi kadar tek seferde",
            "Aynı gün kargo",
        ],
        "rozet": "TAKIM ÇANTASI SETİ",
    },
    {
        "dosya": "meta-ogretmen-endustriyel.png",
        "baslik": "11. sınıf müfredatına birebir",
        "maddeler": [
            "Uygulamalar müfredatla eşleşir",
            "Her öğrenci aynı setle çalışır",
            "Sınıf adedi için bize yazın",
        ],
        "rozet": "ENDÜSTRİYEL ELEKTRONİK SETİ",
    },
    {
        "dosya": "meta-ogretmen-arduino.png",
        "baslik": "Proje dersine hazır set",
        "maddeler": [
            "56 ve 88 parça seçenekleri",
            "Türkçe kaynak ve devre örnekleri",
            "Ders akışı bozulmaz",
        ],
        "rozet": "ARDUINO EĞİTİM SETLERİ",
    },
]

CIKTI_DIZIN = pathlib.Path(__file__).resolve().parents[1] / "posts" / "media" / "meta-ogretmen"


def uret(reklam: dict) -> pathlib.Path:
    tuval, d = _zemin(f"ogretmen:{reklam['dosya']}")
    _marka_baslik(d)

    # Kitleyi eleyen şerit — görselin ilk okunan satırı bu olmalı.
    f_serit = _mono(30)
    gen = _aralikli_genislik(d, SERIT, f_serit, aralik=8)
    _aralikli(d, ((W - gen) / 2, 250), SERIT, f_serit, TURUNCU, aralik=8)

    # Asıl vaat
    fb, satirlar, boyut = _sigdir(
        d, reklam["baslik"], W - 200, [([84, 74], 2), ([64, 56], 3), ([48], 4)]
    )
    satir_y = int(boyut * 1.22)
    y = 400
    for s in satirlar:
        d.text(((W - d.textlength(s, font=fb)) / 2, y), s, font=fb, fill=BEYAZ)
        y += satir_y

    d.line([(W / 2 - 130, y + 34), (W / 2 + 130, y + 34)], fill=TURKUAZ, width=4)

    # Maddeler — solda turkuaz işaret, yanında beyaz metin
    fm = _normal(38)
    fi = _bold(38)
    y = y + 110
    x = 130
    # Isaret + bosluk soldan yer kapiyor; sag kenarda da ayni pay kalsin diye
    # kullanilabilir genislik buna gore hesaplaniyor (yoksa uzun madde sag
    # kenara yapisiyor).
    kullanilabilir = W - (x + 42) - x
    for madde in reklam["maddeler"]:
        f = fm
        while d.textlength(madde, font=f) > kullanilabilir and f.size > 26:
            f = _normal(f.size - 2)
        d.text((x, y + 6), "▪", font=fi, fill=TURKUAZ)
        d.text((x + 42, y), madde, font=f, fill=BEYAZ)
        y += 78

    # Ürün ailesi rozeti
    f_rozet = _mono(26)
    gen = _aralikli_genislik(d, reklam["rozet"], f_rozet, aralik=6)
    _aralikli(d, ((W - gen) / 2, y + 40), reklam["rozet"], f_rozet, GRI, aralik=6)

    _pill(d, "atolyeelektronik.com", 1200)

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
