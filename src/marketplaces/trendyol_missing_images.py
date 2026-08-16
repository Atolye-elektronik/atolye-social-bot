"""
Trendyol ürünlerinde eksik/az/kırık ürün fotoğraflarını tespit eder.

Çalıştırma:
    python src/marketplaces/trendyol_missing_images.py
    python src/marketplaces/trendyol_missing_images.py --min 4 --check-links
    python src/marketplaces/trendyol_missing_images.py --issue   # GitHub issue da aç/güncelle

Ne yapar:
1. Onaylı ürünleri sayfa sayfa çeker
   (V2: GET /product/sellers/{id}/products/approved — V1 filtreleme 10 Ağustos
   2026'da kapatıldı, hesap hâlâ eskiyi veriyorsa client otomatik V1'e düşer).
2. Her ilanı görsel sayısına göre üç kovaya ayırır:
     - FOTOĞRAF YOK   : hiç görsel yok (satışa en çok zarar veren durum)
     - AZ FOTOĞRAF    : görsel sayısı --min değerinin altında (varsayılan 3)
     - KIRIK LİNK     : --check-links verilirse, açılmayan görsel URL'leri
3. Sonucu ekrana basar, state/trendyol_eksik_gorseller.json ve
   raporlar/trendyol_eksik_gorseller.csv dosyalarına yazar.

NOT: V2'de fotoğraflar ilan (content) seviyesindedir, barkod/stok kodu ise
varyant seviyesinde — yani bir ilanın fotoğrafı eksikse o ilandaki tüm
varyantlar etkilenir. Rapor bu yüzden ilan bazlı, varyant barkodları da
satırda listelenir.
"""

import argparse
import csv
import json
from pathlib import Path

import requests

from trendyol_client import iter_all_products

ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = ROOT / "state" / "trendyol_eksik_gorseller.json"
CSV_FILE = ROOT / "raporlar" / "trendyol_eksik_gorseller.csv"

ISSUE_TITLE = "Trendyol: Ürün fotoğrafı eksik ilanlar"

DEFAULT_MIN_IMAGES = 3


def _image_urls(product):
    """İlanın görsel URL listesi. `images: [{"url": ...}]` beklenir, bazı
    yanıtlarda düz string listesi de gelebiliyor."""
    urls = []
    for img in product.get("images") or []:
        if isinstance(img, dict):
            url = img.get("url") or img.get("imageUrl")
        else:
            url = img
        if url:
            urls.append(url)
    return urls


def _normalize(version, product, urls):
    """V1 (düz) ve V2 (content + variants) yanıtlarını tek satır şemasına indirger."""
    variants = product.get("variants") or []

    if version == "v2" and variants:
        barcodes = [v.get("barcode") for v in variants if v.get("barcode")]
        stock_codes = [v.get("stockCode") for v in variants if v.get("stockCode")]
        quantity = sum((v.get("stock") or {}).get("quantity") or 0 for v in variants)
        first_price = (variants[0].get("price") or {})
        sale_price = first_price.get("salePrice")
    else:
        barcodes = [product.get("barcode")] if product.get("barcode") else []
        stock_codes = [product.get("stockCode")] if product.get("stockCode") else []
        quantity = product.get("quantity")
        sale_price = product.get("salePrice")

    return {
        "apiVersion": version,
        "contentId": product.get("contentId") or product.get("productMainId"),
        "title": product.get("title"),
        "brand": product.get("brand"),
        "categoryName": product.get("categoryName"),
        "barcodes": barcodes,
        "stockCodes": stock_codes,
        "variantCount": len(variants) or 1,
        "quantity": quantity,
        "salePrice": sale_price,
        "archived": product.get("archived"),
        "onSale": product.get("onSale", product.get("onsale")),
        "imageCount": len(urls),
        "images": urls,
    }


def _link_ok(url, timeout=10):
    """Görsel gerçekten açılıyor mu? HEAD desteklenmezse GET ile dener."""
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code in (403, 405, 501):
            resp = requests.get(url, timeout=timeout, stream=True)
        return resp.status_code < 400
    except requests.RequestException:
        return False


def scan(min_images=DEFAULT_MIN_IMAGES, check_links=False, include_archived=False):
    no_image, few_images, broken = [], [], []
    total = 0
    versions = set()

    for version, product in iter_all_products():
        if not include_archived and product.get("archived"):
            continue
        total += 1
        versions.add(version)

        urls = _image_urls(product)
        row = _normalize(version, product, urls)

        if not urls:
            no_image.append(row)
        elif len(urls) < min_images:
            few_images.append(row)

        if check_links and urls:
            bad = [u for u in urls if not _link_ok(u)]
            if bad:
                broken.append({**row, "brokenImages": bad})

    return {
        "totalProducts": total,
        "minImages": min_images,
        "apiVersions": sorted(versions),
        "noImage": no_image,
        "fewImages": few_images,
        "brokenImages": broken,
    }


def write_reports(result):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    CSV_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CSV_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["Durum", "İlan (contentId)", "Ürün Adı", "Marka", "Barkodlar",
             "Stok Kodları", "Görsel Sayısı", "Stok", "Fiyat", "Sorunlu Görseller"]
        )
        for label, rows, key in (
            ("FOTOĞRAF YOK", result["noImage"], None),
            ("AZ FOTOĞRAF", result["fewImages"], None),
            ("KIRIK LİNK", result["brokenImages"], "brokenImages"),
        ):
            for r in rows:
                writer.writerow([
                    label, r["contentId"], r["title"], r["brand"],
                    " | ".join(r["barcodes"]), " | ".join(r["stockCodes"]),
                    r["imageCount"], r["quantity"], r["salePrice"],
                    " | ".join(r.get(key) or []) if key else "",
                ])


def _lines(rows, key=None):
    out = []
    for r in rows:
        ident = (r["stockCodes"] or r["barcodes"] or [r["contentId"]])[0]
        line = (f"- **{r['title'] or ident}** "
                f"(contentId: `{r['contentId']}`, barkod: `{', '.join(r['barcodes']) or '-'}`) "
                f"— {r['imageCount']} görsel")
        if key and r.get(key):
            line += f" — açılmayan: {len(r[key])}"
        out.append(line)
    return out


def build_report_text(result):
    parts = [
        f"Toplam **{result['totalProducts']}** ilan tarandı "
        f"(eşik: en az {result['minImages']} görsel, API: {', '.join(result['apiVersions']) or '-'}).\n",
        f"- Fotoğrafı hiç olmayan: **{len(result['noImage'])}**",
        f"- Fotoğrafı yetersiz: **{len(result['fewImages'])}**",
        f"- Kırık görsel linki olan: **{len(result['brokenImages'])}**\n",
    ]
    if result["noImage"]:
        parts.append("### ❌ Hiç fotoğrafı olmayan ilanlar\n")
        parts += _lines(result["noImage"])
        parts.append("")
    if result["fewImages"]:
        parts.append(f"### ⚠️ {result['minImages']} görselden az olan ilanlar\n")
        parts += _lines(result["fewImages"])
        parts.append("")
    if result["brokenImages"]:
        parts.append("### 🔗 Görsel linki açılmayan ilanlar\n")
        parts += _lines(result["brokenImages"], key="brokenImages")
        parts.append("")
    if not (result["noImage"] or result["fewImages"] or result["brokenImages"]):
        parts.append("Tüm ilanların fotoğrafı yeterli görünüyor. ✅")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description="Trendyol eksik ürün fotoğrafı raporu")
    ap.add_argument("--min", type=int, default=DEFAULT_MIN_IMAGES,
                    help=f"Yeterli sayılan minimum görsel sayısı (varsayılan {DEFAULT_MIN_IMAGES})")
    ap.add_argument("--check-links", action="store_true",
                    help="Görsel URL'lerinin gerçekten açıldığını da kontrol et (yavaş)")
    ap.add_argument("--include-archived", action="store_true",
                    help="Arşivlenmiş ilanları da tara")
    ap.add_argument("--issue", action="store_true",
                    help="Sonucu GitHub issue olarak da aç/güncelle")
    args = ap.parse_args()

    result = scan(min_images=args.min, check_links=args.check_links,
                  include_archived=args.include_archived)
    write_reports(result)

    print(build_report_text(result))
    print(f"\nJSON: {STATE_FILE}\nCSV : {CSV_FILE}")

    if args.issue:
        from issue_tracker import upsert_issue
        upsert_issue(
            ISSUE_TITLE,
            build_report_text(result),
            labels=["trendyol", "urun-gorsel"],
            create_if_missing=bool(result["noImage"] or result["fewImages"]),
        )


if __name__ == "__main__":
    main()
