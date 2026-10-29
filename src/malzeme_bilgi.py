"""Bilgilendirici "Bu nedir?" carousel serisi.

Satılan bir malzemeyi (modül, sensör, motor...) anlatır: ne olduğu, nasıl
çalıştığı, hangi projelerde kullanıldığı ve hangi setlerimizde bulunduğu.
Satış değil bilgi odaklı; ürün linki yalnız altyazıda.

İçerik `content/malzeme_bilgi.json`'dan gelir (elle yazılmış, teknik olarak
denetlenmiş metin). Fotoğraf ve link Shopify ürününden (`handle`).

Sıra:
    1 soru       → kanca, malzeme adı geçmez
    2 fotoğraf   → malzemenin kendisi
    3 nedir      → 2-3 madde
    4 nasıl      → bağlantı / çalışma mantığı
    5 projeler   → hangi projelerde kullanılır
    6 setler     → bu parça hangi setlerimizde var

Kullanımı:
    python -m src.malzeme_bilgi --count 2            # sıradaki 2 malzeme
    python -m src.malzeme_bilgi --id l298n --onizleme # post yazmaz
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib

from . import karusel_gorsel
from .shopify_source import STORE_URL, fetch_products

PLATFORMLAR = ["instagram", "facebook", "threads"]

ICERIK_YOLU = pathlib.Path("content/malzeme_bilgi.json")
STATE_PATH = pathlib.Path("state/malzeme_bilgi_seen.json")
POSTS_DIR = pathlib.Path("posts")
MEDIA_DIR = pathlib.Path("posts/media/bilgi")

# Urun postlari 12:00 ve 19:10'da; bilgi postu araya, ogleden sonraya.
YAYIN_SAATI = dt.time(15, 30)
# Seri araligi: iki bilgi postu arasinda kac gun.
ARALIK_GUN = 3


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


def malzemeler() -> list[dict]:
    return json.loads(ICERIK_YOLU.read_text(encoding="utf-8"))["malzemeler"]


def slaytlari_uret(m: dict, urun: dict | None, slug: str) -> list[str]:
    klasor = MEDIA_DIR / slug
    gorsel = ((urun or {}).get("images") or [{}])[0].get("src")
    toplam = 5 + int(bool(gorsel))
    yollar: list[str] = []
    sira = 1

    with karusel_gorsel.Cizer() as cizer:
        yol = klasor / "01-soru.png"
        cizer.kanca("BU NEDİR?", m["soru"], m.get("alt", ""), cikti=yol)
        yollar.append(str(yol))
        sira += 1

        if gorsel:
            yol = klasor / f"{sira:02d}-foto.png"
            cizer.foto("TANIYALIM", m["ad"], gorsel, cikti=yol, sayfa=(sira, toplam))
            yollar.append(str(yol))
            sira += 1

        for dosya, kicker, baslik, anahtar in (
            ("nedir", "NEDİR?", m["ad"], "nedir"),
            ("nasil", "NASIL ÇALIŞIR?", "Bağlantı ve mantık", "nasil"),
            ("projeler", "NE İŞE YARAR?", "Hangi projelerde kullanılır?", "projeler"),
        ):
            yol = klasor / f"{sira:02d}-{dosya}.png"
            cizer.liste(kicker, baslik, m[anahtar], cikti=yol, sayfa=(sira, toplam))
            yollar.append(str(yol))
            sira += 1

        yol = klasor / f"{sira:02d}-setler.png"
        cizer.kapanis(
            "ATÖLYE ELEKTRONİK",
            "Bu parça hangi setlerimizde var?",
            m["setler"][:4],
            cikti=yol,
            alt_bilgi="Tek parça olarak da satışta",
            sayfa=(sira, toplam),
        )
        yollar.append(str(yol))

    return yollar


def _duz(metin: str) -> str:
    return metin.replace("**", "")


def altyazi_kur(m: dict, urun: dict | None) -> str:
    satirlar = [f"🔎 {m['soru']}", "", m.get("alt", ""), "", f"📌 {m['ad']} nedir?"]
    satirlar += [f"• {_duz(x)}" for x in m["nedir"]]
    satirlar += ["", "⚙️ Nasıl çalışır?"] + [f"• {_duz(x)}" for x in m["nasil"]]
    satirlar += ["", "🔧 Hangi projelerde kullanılır?"] + [f"• {_duz(x)}" for x in m["projeler"]]
    satirlar += ["", "📦 Bulunduğu setler: " + ", ".join(m["setler"])]
    if urun and urun.get("handle"):
        satirlar += ["", f"🔗 {STORE_URL}/products/{urun['handle']}"]
    satirlar += ["", "Kaydet, derste lazım olur 📚", "", m.get("etiketler", "#arduino #elektronik #atolyeelektronik")]
    return "\n".join(satirlar)


def _bilgi_gunleri() -> set[dt.date]:
    gunler = set()
    for p in POSTS_DIR.glob("*-bilgi-*.md"):
        try:
            gunler.add(dt.date.fromisoformat(p.name[:10]))
        except ValueError:
            pass
    return gunler


def _siradaki_gun(baslangic: dt.date) -> dt.date:
    """Son bilgi postundan ARALIK_GUN sonrasi; hic yoksa baslangic."""
    gunler = _bilgi_gunleri()
    if not gunler:
        return baslangic
    return max(max(gunler) + dt.timedelta(days=ARALIK_GUN), baslangic)


def uret(count: int = 1, malzeme_id: str | None = None, onizleme: bool = False,
         baslangic: dt.date | None = None) -> list[pathlib.Path]:
    seen = _seen_oku()
    liste = malzemeler()
    if malzeme_id:
        secilen = [m for m in liste if m["id"] == malzeme_id]
    else:
        secilen = [m for m in liste if m["id"] not in seen]
    if not secilen:
        print("Üretilecek yeni bilgi postu yok — content/malzeme_bilgi.json'a malzeme ekle.")
        return []

    urunler = {u.get("handle"): u for u in fetch_products()}
    simdi = dt.datetime.now().astimezone()
    gun = _siradaki_gun(baslangic or (simdi.date() + dt.timedelta(days=1)))
    uretilen: list[pathlib.Path] = []

    for m in secilen[:count]:
        urun = urunler.get(m.get("handle"))
        if urun is None:
            print(f"Uyarı: Shopify ürünü bulunamadı ({m.get('handle')}), fotoğrafsız üretiliyor.")
        slug = f"{gun:%Y-%m-%d}-bilgi-{m['id']}"
        print(f"Slaytlar üretiliyor: {m['ad']}")
        slaytlar = slaytlari_uret(m, urun, slug)
        if onizleme:
            print(f"[önizleme] {len(slaytlar)} slayt, post yazılmadı")
            uretilen += [pathlib.Path(s) for s in slaytlar]
            continue

        ne_zaman = dt.datetime.combine(gun, YAYIN_SAATI)
        yol = POSTS_DIR / f"{slug}.md"
        yol.write_text(
            "---\n"
            f"platforms: [{', '.join(PLATFORMLAR)}]\n"
            f"media: [{', '.join(slaytlar)}]\n"
            f"publish_at: {ne_zaman:%Y-%m-%d %H:%M}\n"
            "---\n"
            f"{altyazi_kur(m, urun)}\n",
            encoding="utf-8",
        )
        uretilen.append(yol)
        seen.add(m["id"])
        print(f"Oluşturuldu: {yol}")
        gun += dt.timedelta(days=ARALIK_GUN)

    if not onizleme:
        _seen_yaz(seen)
    return uretilen


def main() -> None:
    ap = argparse.ArgumentParser(description="Bilgilendirici 'Bu nedir?' carousel'i üret")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--id", help="Sadece bu malzeme (malzeme_bilgi.json id)")
    ap.add_argument("--baslangic", help="İlk yayın günü (YYYY-AA-GG)")
    ap.add_argument("--onizleme", action="store_true")
    a = ap.parse_args()
    bas = dt.date.fromisoformat(a.baslangic) if a.baslangic else None
    uret(a.count, a.id, a.onizleme, bas)


if __name__ == "__main__":
    main()
