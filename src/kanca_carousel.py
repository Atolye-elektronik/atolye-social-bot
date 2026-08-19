"""Shopify ürünlerinden kanca kurgulu, editoryal carousel taslağı üretir.

`carousel_source.py` ile farkı kurguda: orada açılış slaydı ürün adını yazıp
sonra fotoğrafları sıralıyor. Burada açılış slaydı bir **kanca** — kaydırmayı
durduran bir soru ya da iddia. Ürün adı ikinci slaytta çıkıyor.

Sıra:
    1 kanca      → soru/iddia, ürün adı geçmez
    2 fotoğraf   → ürün, editoryal çerçeve içinde
    3 ne var     → öne çıkan maddeler (ürün açıklamasından)
    4 fiyat      → varyant fiyatları, sınıf paketi varsa kademeler
    5 kapanış    → proforma fatura / havale / kargo + WhatsApp

Kullanımı:
    python -m src.kanca_carousel --count 1
    python -m src.kanca_carousel --handle temel-elektronik-deney-seti
    python -m src.kanca_carousel --handle ... --onizleme   # post yazmaz
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re

from . import karusel_gorsel, posts
from .shopify_source import STORE_URL, _slugify, fetch_products, ozet

# Bilerek yalnizca Instagram. Kanca slaydinin altbilgisindeki "Kaydir →"
# ibaresi gorselin icine gomulu ve kaydirma jesti Instagram carousel'ine ait;
# Facebook'ta ayni ibare anlamsiz kaliyor. Ayrica 4:5 oran Instagram profil
# izgarasi icin secildi. Facebook/Threads'e gidecek icerik ayri uretilmeli.
PLATFORMLAR = ["instagram"]

STATE_PATH = pathlib.Path("state/kanca_carousel_seen.json")
KANCA_YOLU = pathlib.Path("content/kancalar.json")
POSTS_DIR = pathlib.Path("posts")
MEDIA_DIR = pathlib.Path("posts/media/kanca")

# Aciklamadan en fazla kac madde cikarilsin. Dortten fazlasi slaytta
# puntoyu dusuruyor ve okunurlugu bozuyor.
MAX_MADDE = 4


def _seen_oku() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        return set(json.loads(STATE_PATH.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return set()


def _seen_yaz(seen: set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _tl(deger) -> str:
    """'1588.00' -> '1.588 ₺' — kurus sifirsa gosterilmiyor."""
    try:
        sayi = float(deger)
    except (TypeError, ValueError):
        return ""
    tam = f"{int(sayi):,}".replace(",", ".")
    kurus = round((sayi - int(sayi)) * 100)
    return f"{tam},{kurus:02d} ₺" if kurus else f"{tam} ₺"


def kanca_sec(urun: dict) -> dict:
    """Ürüne uygun kancalardan birini seçer.

    Seçim ürün kimliğinden türüyor: aynı ürün her çalıştırmada aynı kancayı
    alıyor (taslak yeniden üretilince görsel değişmesin), ürünler arasında ise
    dağılıyor.

    Kimlik doğrudan modülo'ya sokulmuyor: Shopify ürün kimliklerinin **hepsi
    tek sayı** (77 üründe `id % 4` her seferinde 1 çıkıyor). Havuz boyutu çift
    olduğunda modülo tek bir değere çöküyor ve tüm ürünler aynı kancayı alıyordu
    — 27 ürün tek bir kancaya yığılmıştı. Kimliğin özetini almak dağılımı
    düzeltiyor, belirliliği bozmuyor.
    """
    veri = json.loads(KANCA_YOLU.read_text(encoding="utf-8"))
    kancalar = veri["kancalar"]
    baslik = (urun.get("title") or "").lower()

    uygun = [k for k in kancalar if any(a in baslik for a in k["anahtar"])]
    if not uygun:
        uygun = [k for k in kancalar if not k["anahtar"]]

    ozet = hashlib.sha256(str(urun.get("id", "")).encode()).hexdigest()
    return uygun[int(ozet, 16) % len(uygun)]


def maddeler_cikar(urun: dict) -> list[str]:
    """Ürün açıklamasından slayta uygun kısa maddeler çıkarır."""
    metin = ozet(urun.get("body_html", ""))
    if not metin:
        return []

    # Cumlelere bol; slaytta iki satiri gecmeyecek kadar kisa olanlari al.
    cumleler = [c.strip() for c in re.split(r"(?<=[.!?])\s+", metin) if c.strip()]
    secilen = [c for c in cumleler if 25 <= len(c) <= 115]
    return secilen[:MAX_MADDE]


def fiyat_satirlari(urun: dict) -> list[dict]:
    """Varyantları fiyat satırına çevirir; tek varyantlıysa tek satır."""
    varyantlar = urun.get("variants") or []
    satirlar = []
    for v in varyantlar[:4]:
        ad = (v.get("title") or "").strip()
        if ad.lower() in ("default title", ""):
            ad = urun.get("title", "")[:38]
        satirlar.append({
            "ad": ad,
            "aciklama": "stokta" if v.get("available") else "",
            "deger": _tl(v.get("price")),
            "birim": "",
            "vurgu": len(varyantlar) > 1 and v is varyantlar[-1],
        })
    return satirlar


def slaytlari_uret(urun: dict, slug: str) -> list[str]:
    klasor = MEDIA_DIR / slug
    baslik = (urun.get("title") or "").strip()
    kanca = kanca_sec(urun)
    maddeler = maddeler_cikar(urun)
    fiyatlar = fiyat_satirlari(urun)
    gorseller = [g["src"] for g in (urun.get("images") or [])]

    # Slayt sayisi icerige gore degisiyor; sayfa sayaci icin once toplami bul.
    var_madde = bool(maddeler)
    var_fiyat = bool(fiyatlar)
    var_foto = bool(gorseller)
    # Magaza gorsellerinde paket icerigini adetleriyle gosteren panel
    # "-icerik" adiyla yukleniyor; varsa carousel'e ayri slayt olarak girer.
    icerik_gorsel = next(
        (g for g in gorseller if "icerik" in g.rsplit("/", 1)[-1].lower()), None
    )
    var_icerik = bool(icerik_gorsel)
    toplam = 2 + int(var_foto) + int(var_icerik) + int(var_madde) + int(var_fiyat)

    yollar: list[str] = []
    sira = 1

    with karusel_gorsel.Cizer() as cizer:
        yol = klasor / "01-kanca.png"
        cizer.kanca(
            kanca["etiket"],
            kanca["kanca"].format(urun=baslik, fiyat=_tl((urun.get("variants") or [{}])[0].get("price"))),
            kanca["alt"],
            cikti=yol,
        )
        yollar.append(str(yol))
        sira += 1

        if var_foto:
            yol = klasor / f"{sira:02d}-urun.png"
            cizer.foto("ÜRÜN", baslik, gorseller[0], cikti=yol, sayfa=(sira, toplam))
            yollar.append(str(yol))
            sira += 1

        if var_icerik:
            yol = klasor / f"{sira:02d}-icerik.png"
            cizer.foto("İÇİNDEKİLER", "Paket içeriği ve adetler", icerik_gorsel,
                       cikti=yol, sayfa=(sira, toplam))
            yollar.append(str(yol))
            sira += 1

        if var_madde:
            yol = klasor / f"{sira:02d}-ozellik.png"
            cizer.liste("NE VAR İÇİNDE", "Öne çıkanlar", maddeler, cikti=yol,
                        sayfa=(sira, toplam))
            yollar.append(str(yol))
            sira += 1

        if var_fiyat:
            yol = klasor / f"{sira:02d}-fiyat.png"
            cizer.satirlar("FİYAT", "Güncel fiyat", "", fiyatlar, cikti=yol,
                           alt_bilgi="1.200 ₺ üzeri kargo bedava", sayfa=(sira, toplam))
            yollar.append(str(yol))
            sira += 1

        yol = klasor / f"{sira:02d}-kapanis.png"
        cizer.kapanis(
            "SİPARİŞ",
            "Okullara ve kurumlara",
            [
                "**Proforma fatura** düzenliyoruz",
                "**Havale/EFT** ile ödeme, kredi kartı zorunlu değil",
                "**1.200 ₺ üzeri kargo bedava**, tek koli teslim",
                "Sınıf mevcuduna göre **özel adet ve fiyat**",
            ],
            cikti=yol,
            sayfa=(sira, toplam),
        )
        yollar.append(str(yol))

    return yollar


def altyazi_kur(urun: dict, kanca: dict) -> str:
    baslik = (urun.get("title") or "").strip()
    aciklama = ozet(urun.get("body_html", ""))

    satirlar = [kanca["kanca"].format(urun=baslik, fiyat=_tl((urun.get("variants") or [{}])[0].get("price")))]
    satirlar += ["", kanca["alt"], "", f"👉 {baslik}"]
    if aciklama:
        satirlar += ["", aciklama]
    satirlar += [
        "",
        "Okullara proforma fatura, havale/EFT ile ödeme, 1.200 ₺ üzeri kargo bedava.",
        "Sınıf mevcudunuzu yazın, aynı gün fiyat çıkaralım.",
    ]
    if urun.get("handle"):
        satirlar += ["", f"🔗 {STORE_URL}/products/{urun['handle']}"]
    satirlar += [
        "",
        "#mesleklisesi #elektrikelektronik #bilisimteknolojileri #arduino #robotik "
        "#stem #atolyeelektronik #ogretmen #meslekiegitim #mtal",
    ]
    return "\n".join(satirlar)


def post_yaz(urun: dict, slug: str, slaytlar: list[str], ne_zaman: dt.datetime) -> pathlib.Path:
    yol = POSTS_DIR / f"{slug}.md"
    govde = (
        "---\n"
        f"platforms: [{', '.join(PLATFORMLAR)}]\n"
        f"media: [{', '.join(slaytlar)}]\n"
        f"publish_at: {ne_zaman:%Y-%m-%d %H:%M}\n"
        "---\n"
        f"{altyazi_kur(urun, kanca_sec(urun))}\n"
    )
    yol.write_text(govde, encoding="utf-8")
    return yol


# Kanca carousel'i icin sabit yayin saati. Uretim saatine +24 saat eklemek
# 03:10 gibi olu saatlere denk geliyordu (is sabah erken calisiyor).
YAYIN_SAATI = 12


def _bos_gun(bugun: dt.date) -> dt.date:
    """Hicbir postun planlanmadigi ilk gunu bulur (yarindan itibaren).

    Once kosulsuz "yarin" deniyordu, takvimde ne oldugu umursanmiyordu. Sonuc
    18 Agustos'ta dort post oldu ve ikisi ayni urundu. Dolu gunler atlanarak
    gunde bir gonderi korunuyor.
    """
    dolu = {p.publish_at.date() for p in posts.load_all(POSTS_DIR) if p.publish_at}

    gun = bugun + dt.timedelta(days=1)
    # 400 gun: sonsuz donguye karsi emniyet. Takvim bu kadar doluysa zaten
    # uretmeye devam etmenin anlami yok.
    for _ in range(400):
        if gun not in dolu:
            return gun
        gun += dt.timedelta(days=1)
    return gun


def uret(count: int = 1, start_in_hours: int = 24, spacing_hours: int = 24,
         handle: str | None = None, onizleme: bool = False) -> list[pathlib.Path]:
    seen = _seen_oku()
    urunler = fetch_products()

    if handle:
        secilen = [u for u in urunler if u.get("handle") == handle]
        if not secilen:
            print(f"Ürün bulunamadı: {handle}")
            return []
    else:
        secilen = [u for u in urunler if str(u.get("id")) not in seen]
        # Fotografi olan urunler once: ikinci slayt onlarda dolu cikiyor.
        secilen.sort(key=lambda u: len(u.get("images") or []), reverse=True)

    if not secilen:
        print("Kanca carousel'i üretilecek yeni ürün yok.")
        return []

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    uretilen: list[pathlib.Path] = []
    simdi = dt.datetime.now().astimezone()
    ne_zaman = dt.datetime.combine(
        _bos_gun(simdi.date()), dt.time(YAYIN_SAATI, 0), tzinfo=simdi.tzinfo
    )

    for urun in secilen[:count]:
        slug = f"{ne_zaman:%Y-%m-%d}-kanca-{_slugify(urun.get('handle') or urun.get('title', ''))}"
        if (POSTS_DIR / f"{slug}.md").exists():
            ne_zaman += dt.timedelta(hours=spacing_hours)
            continue

        print(f"Slaytlar üretiliyor: {urun.get('title')}")
        slaytlar = slaytlari_uret(urun, slug)

        if onizleme:
            print(f"[önizleme] {len(slaytlar)} slayt üretildi, post yazılmadı:")
            for s in slaytlar:
                print(f"  {s}")
            return [pathlib.Path(s) for s in slaytlar]

        yol = post_yaz(urun, slug, slaytlar, ne_zaman)
        uretilen.append(yol)
        seen.add(str(urun["id"]))
        ne_zaman += dt.timedelta(hours=spacing_hours)
        print(f"Oluşturuldu: {yol} ({len(slaytlar)} slayt)")

    if not onizleme:
        _seen_yaz(seen)
    return uretilen


def main() -> None:
    ayristirici = argparse.ArgumentParser(description="Kanca kurgulu carousel taslağı üret")
    ayristirici.add_argument("--count", type=int, default=1)
    ayristirici.add_argument("--start-in-hours", type=int, default=24)
    ayristirici.add_argument("--spacing-hours", type=int, default=24)
    ayristirici.add_argument("--handle", help="Sadece bu ürün (Shopify handle)")
    ayristirici.add_argument("--onizleme", action="store_true",
                             help="Slaytları üret ama post dosyası yazma")
    args = ayristirici.parse_args()
    uret(args.count, args.start_in_hours, args.spacing_hours, args.handle, args.onizleme)


if __name__ == "__main__":
    main()
