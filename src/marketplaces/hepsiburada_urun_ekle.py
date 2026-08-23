"""
Shopify'daki son N ürünü Hepsiburada'ya ürün olarak açar.

İki aşamalı bir iş — Hepsiburada'da ürün açmakla ürünü satışa koymak ayrı şeyler:

  1. KATALOG  (bu betik)  ürün bilgisi MPOP'a gönderilir, Hepsiburada onaylar
                          ve ürüne bir hepsiburadaSku verir.
  2. LİSTELEME            onay sonrası fiyat + stok listing API'sine yazılır —
                          hepsiburada_update_price_stock.py bunu yapıyor.

Kullanım:
    # Ne gönderileceğini gösterir, hiçbir şey göndermez (varsayılan):
    python hepsiburada_urun_ekle.py --count 7

    # Payload'ı dosyaya yazar, gözden geçirmek için:
    python hepsiburada_urun_ekle.py --count 7 --cikti payload.json

    # Gerçekten gönderir:
    python hepsiburada_urun_ekle.py --count 7 --gonder

    # Kategori ID'si bulmak için:
    python hepsiburada_urun_ekle.py --kategori-ara "robot"

Kategori eşlemesi content/hepsiburada_kategori.json dosyasından okunur;
Shopify'daki product_type -> Hepsiburada categoryId + o kategorinin zorunlu
sabit özellikleri. Kategori ID'si girilmemiş ürünler atlanır.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

import requests

try:
    import hepsiburada_catalog as katalog
except ImportError:  # paket olarak import edildiğinde
    from . import hepsiburada_catalog as katalog

KOK = Path(__file__).resolve().parents[2]
KATEGORI_DOSYASI = KOK / "content" / "hepsiburada_kategori.json"
DURUM_DOSYASI = KOK / "state" / "hepsiburada_urunler.json"

STORE_URL = os.environ.get("STORE_URL", "https://atolyeelektronik.com").rstrip("/")
MARKA = os.environ.get("HEPSIBURADA_MARKA", "Atölye Elektronik")
KDV_ORANI = os.environ.get("HEPSIBURADA_KDV", "20")
GARANTI_AY = os.environ.get("HEPSIBURADA_GARANTI_AY", "24")

# Hepsiburada ürün adı için üst sınır koyuyor; uzun Shopify başlıkları kırpılır.
URUN_ADI_MAX = 100


# --- Shopify ---------------------------------------------------------------

SHOPIFY_STORE = os.environ.get("SHOPIFY_STORE", "").strip()
SHOPIFY_TOKEN = os.environ.get("SHOPIFY_ADMIN_TOKEN", "").strip()
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2025-07")


def _shopify_admin(count: int) -> list[dict]:
    """Admin API üzerinden son N ürün.

    Herkese açık products.json barkod alanını hiç döndürmüyor — Hepsiburada'nın
    zorunlu tuttuğu alan tam da o olduğu için, token varsa Admin API'yi
    kullanıyoruz ki Shopify'a girilmiş barkodlar görülebilsin."""
    resp = requests.get(
        f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products.json",
        params={"limit": count, "order": "created_at desc"},
        headers={"X-Shopify-Access-Token": SHOPIFY_TOKEN},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json().get("products", [])


def _shopify_public(count: int) -> list[dict]:
    """Token yoksa herkese açık ürün listesi — repo'daki shopify_source.py ile
    aynı yol. Barkod ve ağırlık bilgisi burada eksik olabilir."""
    resp = requests.get(
        f"{STORE_URL}/products.json",
        params={"limit": 250},
        headers={"User-Agent": "atolye-hepsiburada-sync"},
        timeout=60,
    )
    resp.raise_for_status()
    urunler = resp.json().get("products", [])
    urunler.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return urunler[:count]


def shopify_urunleri(count: int) -> tuple[list[dict], list[str]]:
    if SHOPIFY_STORE and SHOPIFY_TOKEN:
        return _shopify_admin(count), []
    return _shopify_public(count), [
        "SHOPIFY_ADMIN_TOKEN tanımlı değil — herkese açık products.json kullanıldı. "
        "Bu liste barkod alanını içermez, Shopify'a girilmiş barkodlar görülemez."
    ]


# --- Yardımcılar -----------------------------------------------------------

def temiz_aciklama(raw: str, limit: int = 4000) -> str:
    """Hepsiburada açıklamada basit HTML kabul ediyor ama script/style ve
    boş satır yığınlarını istemiyor. Fazlasını da kırpıyoruz."""
    metin = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw or "", flags=re.S | re.I)
    metin = re.sub(r"\n\s*\n+", "\n", metin).strip()
    if len(metin) > limit:
        metin = metin[:limit].rsplit("<", 1)[0].rstrip()
    return metin


def ean13(govde12: str) -> str:
    """12 haneli gövdeye EAN-13 kontrol hanesi ekler."""
    toplam = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(govde12))
    return govde12 + str((10 - toplam % 10) % 10)


def barkod_uret(sku: str, prefix: str) -> str:
    """SKU'dan sabit (deterministik) bir EAN-13 üretir — aynı SKU her zaman
    aynı barkodu verir, böylece betik iki kez çalışsa da barkod değişmez.

    prefix olarak 200-299 aralığı kullanılmalı: GS1 bu aralığı mağaza içi /
    kısıtlı dağıtım için ayırmıştır, yani kimsenin tescilli barkoduyla
    çakışmaz. Kalıcı çözüm GS1 Türkiye'den kendi firma önekini almaktır."""
    import hashlib

    h = hashlib.sha1(sku.encode("utf-8")).hexdigest()
    sayisal = str(int(h[:12], 16))[:12 - len(prefix)].rjust(12 - len(prefix), "0")
    return ean13(prefix + sayisal)


def ad_kisalt(ad: str, limit: int = URUN_ADI_MAX) -> tuple[str, str | None]:
    """Ürün adını Hepsiburada sınırına sığdırır.

    Doğrudan kesmek "... (Bluetooth + IR Kumanda + Engelden" gibi cümle
    ortasında biten adlar üretiyordu. Onun yerine önce sondaki parantezli
    açıklamaları atıyoruz — bilgi kaybı oluyor ama ad okunur kalıyor.
    Yine sığmazsa son çare kelime sınırından kesiyoruz."""
    if len(ad) <= limit:
        return ad, None

    kisa = ad
    while len(kisa) > limit:
        yeni = re.sub(r"\s*[(\[][^()\[\]]*[)\]]\s*$", "", kisa).strip()
        if yeni == kisa:
            break
        kisa = yeni
    if len(kisa) <= limit:
        return kisa, "ürün adı sınıra sığması için sondaki parantezli açıklama atıldı"

    kisa = kisa[:limit].rsplit(" ", 1)[0].rstrip(" -—–,")
    return kisa, f"ürün adı {limit} karaktere kırpıldı"


def varyant_adi(baslik: str, varyant: str) -> str:
    """Varyantlı üründe Hepsiburada'ya gidecek ürün adını kurar.

    Shopify başlığı çoğu zaman seçenekleri de sayıyor ("Sınıf Paketi
    (10 / 20 / 30 Adet)"). Tek varyant için ürün açarken bu liste yanıltıcı
    olur — "(10 / 20 / 30 Adet) - 10 Adet" gibi bir ad çıkar. O yüzden içinde
    '/' geçen parantezli seçenek listelerini atıyoruz."""
    temiz = re.sub(r"\s*[(\[][^()\[\]]*/[^()\[\]]*[)\]]", "", baslik)
    temiz = re.sub(r"\s{2,}", " ", temiz).strip(" -—–")
    return f"{temiz} - {varyant}"


def kategori_haritasi(yol: Path | None = None) -> dict:
    yol = yol or KATEGORI_DOSYASI
    if not yol.exists():
        raise SystemExit(
            f"Kategori eşleme dosyası yok: {yol}\n"
            "Önce --kategori-ara ile categoryId'leri bul ve dosyayı doldur."
        )
    return json.loads(yol.read_text(encoding="utf-8"))


def gonderilmisler() -> dict:
    if not DURUM_DOSYASI.exists():
        return {}
    try:
        return json.loads(DURUM_DOSYASI.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def durum_kaydet(kayit: dict) -> None:
    DURUM_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    DURUM_DOSYASI.write_text(
        json.dumps(kayit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# --- Payload kurulumu ------------------------------------------------------

def hb_urunu_kur(urun: dict, varyant: dict, kategori: dict, barkod_prefix: str | None):
    """Bir Shopify varyantından bir Hepsiburada ürün kaydı üretir.

    Döner: (payload, uyarilar). payload None ise ürün gönderilemez."""
    uyarilar = []
    sku = (varyant.get("sku") or "").strip()
    if not sku:
        return None, [f"{urun['title']}: varyantın SKU'su yok, atlandı"]

    barkod = (varyant.get("barcode") or "").strip()
    if not barkod:
        if not barkod_prefix:
            return None, [
                f"{sku}: barkod yok. Shopify'a barkod gir ya da --barkod-uret ile üret."
            ]
        barkod = barkod_uret(sku, barkod_prefix)
        uyarilar.append(f"{sku}: barkod yoktu, üretildi -> {barkod}")

    cok_varyantli = len(urun.get("variants", [])) > 1
    # Eşleme dosyasındaki ad_override, o SKU için başlığı tamamen değiştirir —
    # otomatik kısaltmanın iyi sonuç vermediği ürünler için kaçış kapısı.
    ad = (kategori.get("ad_override") or {}).get(sku)
    if ad:
        uyarilar.append(f"{sku}: ad eşleme dosyasından alındı -> {ad}")
    else:
        ad = urun["title"]
        if cok_varyantli and varyant.get("title") and varyant["title"] != "Default Title":
            ad = varyant_adi(ad, varyant["title"])
    ad, kisaltma_notu = ad_kisalt(ad)
    if kisaltma_notu:
        uyarilar.append(f"{sku}: {kisaltma_notu}")

    gorseller = [g["src"] for g in urun.get("images", [])][:5]
    if not gorseller:
        return None, [f"{sku}: görsel yok, Hepsiburada en az 1 görsel istiyor"]

    # Hepsiburada'nın "kg" alanı aslında desi. Öncelik sırası: eşleme
    # dosyasındaki SKU bazlı desi > Shopify ağırlığı > kategori varsayılanı.
    # Öncelik: SKU bazlı istisna > kategorinin bilinen desisi > Shopify
    # ağırlığı > kategori varsayılanı (bu sonuncusu tahmindir, uyarır).
    desi_ozel = (kategori.get("desi_override") or {}).get(sku)
    agirlik = varyant.get("grams") or 0
    if desi_ozel is not None:
        kg = desi_ozel
    elif kategori.get("desi") is not None:
        kg = kategori["desi"]
    elif agirlik:
        kg = agirlik / 1000
    else:
        kg = kategori.get("varsayilan_kg", 1)
        uyarilar.append(
            f"{sku}: desi bilinmiyor, {kg} varsayıldı (kargo ücretini etkiler)"
        )
    # Desi tam sayı olarak gidiyor. Yukarı yuvarlıyoruz: aşağı yuvarlamak
    # eksik beyan olur ve aradaki kargo farkını satıcı öder.
    kg = math.ceil(float(kg))

    ozellikler = {
        "merchantSku": sku,
        "Barcode": barkod,
        "UrunAdi": ad,
        "UrunAciklamasi": temiz_aciklama(urun.get("body_html", "")),
        "Marka": urun.get("vendor") or MARKA,
        "GarantiSuresi": int(GARANTI_AY),
        # Hepsiburada bu alanı "Desi" olarak gösteriyor — kilogram değil,
        # hacimsel ağırlık. Shopify'da gerçek ağırlık varsa ondan, yoksa
        # kategori varsayılanından geliyor.
        "kg": kg,
        "tax_vat_rate": KDV_ORANI,
        # Paket Görseli (ön) kategorilerin çoğunda zorunlu; ürünün ilk
        # görselini kullanıyoruz.
        "00000MU": gorseller[0],
    }
    for i, src in enumerate(gorseller, start=1):
        ozellikler[f"Image{i}"] = src

    # Katalog ucu fiyat ve stoğu da kabul ediyor (kategori şemasında opsiyonel
    # alanlar olarak duruyorlar), böylece onay sonrası ayrıca listeleme
    # yapmaya gerek kalmıyor.
    # Pazar yeri fiyatı web fiyatından farklıysa eşleme dosyasındaki
    # fiyat_override (SKU -> fiyat) önceliklidir (komisyon+kargo farkı).
    fiyat = (kategori.get("fiyat_override") or {}).get(sku) or varyant.get("price")
    if fiyat:
        ozellikler["price"] = str(fiyat)
    # Stok: herkese açık Shopify listesi bu alanı vermiyor, o yüzden eşleme
    # dosyasındaki SKU bazlı değer devreye giriyor. Admin token tanımlıysa
    # Shopify'ın kendi sayısı önceliklidir.
    stok = varyant.get("inventory_quantity")
    if stok is None:
        stok = (kategori.get("stok_override") or {}).get(sku)
    if stok is not None:
        ozellikler["stock"] = str(max(int(stok), 0))
    else:
        uyarilar.append(f"{sku}: stok bilgisi yok, alan boş gidiyor")

    if cok_varyantli:
        ozellikler["VaryantGroupID"] = urun["handle"]

    # Kategoriye özel zorunlu alanlar (renk, materyal, yaş grubu...) eşleme
    # dosyasından gelir; ürün bazlı override'lar onun üstüne yazılır.
    ozellikler.update(kategori.get("sabit_ozellikler", {}))

    payload = {
        "categoryId": kategori["categoryId"],
        "merchant": katalog.MERCHANT_ID,
        "attributes": ozellikler,
    }
    return payload, uyarilar


def payload_kur(count: int, barkod_prefix: str | None, tekrar: bool,
                kategori_dosyasi: Path | None = None):
    harita = kategori_haritasi(kategori_dosyasi)
    onceki = gonderilmisler()
    urunler, kaynak_uyarilari = shopify_urunleri(count)

    payloadlar, atlanan = [], []
    uyarilar = list(kaynak_uyarilari)

    for urun in urunler:
        tur = urun.get("product_type") or ""
        kategori = harita.get(tur) or harita.get("varsayilan") or {}
        if not kategori.get("categoryId"):
            atlanan.append(
                f"{urun['title']}: '{tur}' için categoryId tanımlı değil "
                f"({KATEGORI_DOSYASI.name})"
            )
            continue

        for varyant in urun.get("variants", []):
            sku = (varyant.get("sku") or "").strip()
            if sku in (kategori.get("sku_atla") or []):
                atlanan.append(f"{sku}: sku_atla listesinde, pazar yerine konmuyor")
                continue
            if sku and sku in onceki and not tekrar:
                atlanan.append(f"{sku}: daha önce gönderilmiş, atlandı (--tekrar ile zorla)")
                continue
            payload, mesajlar = hb_urunu_kur(urun, varyant, kategori, barkod_prefix)
            if payload is None:
                # payload kurulamadıysa mesajlar uyarı değil, atlanma sebebidir
                atlanan.extend(mesajlar or [f"{sku}: kurulamadı"])
            else:
                uyarilar.extend(mesajlar)
                payloadlar.append(payload)

    return payloadlar, uyarilar, atlanan


# --- CLI -------------------------------------------------------------------

def kategori_ara(kelime: str) -> None:
    sonuc = katalog.search_categories(kelime)
    if not sonuc:
        print(f"'{kelime}' için kategori bulunamadı.")
        return
    print(f"'{kelime}' için {len(sonuc)} kategori:")
    for cat in sonuc:
        print(f"  {cat.get('categoryId', cat.get('id'))}  {cat.get('name')}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Shopify ürünlerini Hepsiburada'ya aç")
    ap.add_argument("--count", type=int, default=7, help="Son kaç ürün (varsayılan 7)")
    ap.add_argument("--gonder", action="store_true",
                    help="Gerçekten gönder. Verilmezse sadece ne gideceğini gösterir.")
    ap.add_argument("--cikti", help="Payload'ı bu JSON dosyasına yaz")
    ap.add_argument("--barkod-uret", metavar="PREFIX", nargs="?", const="290",
                    help="Barkodu olmayan ürünler için EAN-13 üret (GS1 mağaza içi "
                         "aralığı: 200-299, varsayılan 290)")
    ap.add_argument("--tekrar", action="store_true",
                    help="Daha önce gönderilmiş SKU'ları da tekrar gönder")
    ap.add_argument("--duz-json", action="store_true",
                    help="form-data yerine düz JSON gövde gönder (çalışmıyor, "
                         "sadece karşılaştırma için)")
    ap.add_argument("--kategori-ara", metavar="KELIME",
                    help="Hepsiburada kategorilerinde arama yapar, categoryId gösterir")
    ap.add_argument("--kategori-dosyasi", metavar="YOL", type=Path,
                    help=f"Eşleme dosyasının yolu (varsayılan {KATEGORI_DOSYASI})")
    args = ap.parse_args()

    if args.kategori_ara:
        kategori_ara(args.kategori_ara)
        return

    payloadlar, uyarilar, atlanan = payload_kur(
        args.count, args.barkod_uret, args.tekrar, args.kategori_dosyasi
    )

    if uyarilar:
        print("UYARILAR:")
        for u in uyarilar:
            print(f"  ! {u}")
        print()
    if atlanan:
        print("ATLANANLAR:")
        for a in atlanan:
            print(f"  - {a}")
        print()

    print(f"Gönderilmeye hazır {len(payloadlar)} ürün:")
    for p in payloadlar:
        oz = p["attributes"]
        print(f"  • {oz['merchantSku']:<18} {oz['Barcode']}  {oz['UrunAdi']}")

    if args.cikti:
        Path(args.cikti).write_text(
            json.dumps(payloadlar, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nPayload yazıldı: {args.cikti}")

    if not payloadlar:
        return

    if not args.gonder:
        print("\n(Kuru çalıştırma — hiçbir şey gönderilmedi. Göndermek için --gonder ekle.)")
        return

    sonuc = katalog.create_products(payloadlar, multipart=not args.duz_json)
    print("\nHepsiburada yanıtı:", json.dumps(sonuc, ensure_ascii=False, indent=2))

    tracking = sonuc.get("data", {}).get("trackingId") or sonuc.get("trackingId")
    kayit = gonderilmisler()
    for p in payloadlar:
        kayit[p["attributes"]["merchantSku"]] = {
            "barkod": p["attributes"]["Barcode"],
            "trackingId": tracking,
        }
    durum_kaydet(kayit)

    if tracking:
        print(f"\nDurum sorgulamak için:\n  trackingId = {tracking}")
        print("  python -c \"import hepsiburada_catalog as k, json; "
              f"print(json.dumps(k.get_import_status('{tracking}'), indent=2))\"")


if __name__ == "__main__":
    sys.exit(main())
