"""Carousel slide'larini Shopify CDN'ine yukler ve post dosyalarini gunceller.

Neden gerekli:
  Instagram, paylasilacak gorselin internetten erisilebilir olmasini sart
  kosuyor. Gorseller repoda durdugu surece deponun public olmasi gerekiyordu.
  Bu arac slide'lari Shopify'in dosya kutuphanesine tasiyor; boylece depo
  private kalabiliyor ve gorseller magazanin CDN'inden servis ediliyor.

Uretilen eslesme state/shopify_medya.json dosyasinda tutulur, ayni dosya
iki kez yuklenmez.

Kullanimi (SHOPIFY_ADMIN_TOKEN ve SHOPIFY_STORE tanimli olmali):
    python tools/shopify_medya_yukle.py            # eksikleri yukle + postlari guncelle
    python tools/shopify_medya_yukle.py --sadece-yukle
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time

import requests

MAGAZA = os.environ.get("SHOPIFY_STORE", "").strip()
TOKEN = os.environ.get("SHOPIFY_ADMIN_TOKEN", "").strip()
SURUM = os.environ.get("SHOPIFY_API_VERSION", "2025-07")

ESLESME = pathlib.Path("state/shopify_medya.json")
MEDYA_KOK = pathlib.Path("posts/media/carousel")
POSTS = pathlib.Path("posts")


def _api() -> str:
    if not MAGAZA or not TOKEN:
        raise SystemExit("SHOPIFY_STORE ve SHOPIFY_ADMIN_TOKEN tanimli olmali.")
    ad = MAGAZA if MAGAZA.endswith(".myshopify.com") else f"{MAGAZA}.myshopify.com"
    return f"https://{ad}/admin/api/{SURUM}/graphql.json"


def _gql(sorgu: str, degiskenler: dict) -> dict:
    r = requests.post(
        _api(),
        headers={"X-Shopify-Access-Token": TOKEN, "Content-Type": "application/json"},
        json={"query": sorgu, "variables": degiskenler},
        timeout=120,
    )
    r.raise_for_status()
    veri = r.json()
    if "errors" in veri:
        raise RuntimeError(veri["errors"])
    return veri["data"]


STAGED = """
mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets { url resourceUrl parameters { name value } }
    userErrors { field message }
  }
}
"""

FILE_CREATE = """
mutation fileCreate($files: [FileCreateInput!]!) {
  fileCreate(files: $files) {
    files { id fileStatus }
    userErrors { field message }
  }
}
"""

FILE_URL = """
query n($id: ID!) {
  node(id: $id) { ... on MediaImage { fileStatus image { url } } }
}
"""


def _yukle(yol: pathlib.Path, ad: str) -> str:
    """Tek dosyayi yukler, kalici CDN adresini dondurur."""
    d = _gql(STAGED, {"input": [{
        "filename": ad, "mimeType": "image/jpeg",
        "resource": "FILE", "httpMethod": "POST",
    }]})
    hedef = d["stagedUploadsCreate"]["stagedTargets"][0]

    alanlar = [(p["name"], (None, p["value"])) for p in hedef["parameters"]]
    with open(yol, "rb") as f:
        alanlar.append(("file", (ad, f, "image/jpeg")))
        r = requests.post(hedef["url"], files=alanlar, timeout=180)
    r.raise_for_status()

    d = _gql(FILE_CREATE, {"files": [{
        "originalSource": hedef["resourceUrl"],
        "contentType": "IMAGE",
        "alt": f"Atolye Elektronik - {ad}",
    }]})
    dosya_id = d["fileCreate"]["files"][0]["id"]

    # islenmesini bekle
    for _ in range(30):
        d = _gql(FILE_URL, {"id": dosya_id})
        dugum = d.get("node") or {}
        if dugum.get("fileStatus") == "READY" and (dugum.get("image") or {}).get("url"):
            return dugum["image"]["url"]
        time.sleep(4)
    raise RuntimeError(f"Dosya islenemedi: {ad}")


def _yukle_hepsi(eslesme: dict) -> dict:
    dosyalar = sorted(MEDYA_KOK.rglob("*.jpg"))
    yeni = [d for d in dosyalar if str(d) not in eslesme]
    print(f"{len(dosyalar)} slide, {len(yeni)} tanesi yuklenecek")

    for i, yol in enumerate(yeni, 1):
        # dosya adi benzersiz olsun: klasor + dosya
        ad = f"{yol.parent.name}--{yol.name}"
        try:
            eslesme[str(yol)] = _yukle(yol, ad)
            print(f"  [{i}/{len(yeni)}] {yol.name} -> yuklendi")
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}/{len(yeni)}] {yol} HATA: {exc}")
        if i % 10 == 0:
            _kaydet(eslesme)
    return eslesme


def _kaydet(eslesme: dict) -> None:
    ESLESME.parent.mkdir(parents=True, exist_ok=True)
    ESLESME.write_text(json.dumps(eslesme, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _yukle_eslesme() -> dict:
    if not ESLESME.exists():
        return {}
    try:
        return json.loads(ESLESME.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _postlari_guncelle(eslesme: dict) -> int:
    """Post dosyalarindaki yerel yollari CDN adresleriyle degistirir."""
    degisen = 0
    for md in sorted(POSTS.glob("*.md")):
        metin = md.read_text(encoding="utf-8")
        yeni = metin
        for yerel, cdn in eslesme.items():
            if yerel in yeni:
                yeni = yeni.replace(yerel, cdn)
        if yeni != metin:
            md.write_text(yeni, encoding="utf-8")
            degisen += 1
            print(f"  guncellendi: {md.name}")
    return degisen


def main() -> None:
    ap = argparse.ArgumentParser(description="Carousel slide'larini Shopify CDN'ine yukle")
    ap.add_argument("--sadece-yukle", action="store_true", help="Post dosyalarina dokunma")
    args = ap.parse_args()

    eslesme = _yukle_eslesme()
    eslesme = _yukle_hepsi(eslesme)
    _kaydet(eslesme)
    print(f"toplam eslesme: {len(eslesme)}")

    if not args.sadece_yukle:
        print("post dosyalari guncelleniyor...")
        print(f"{_postlari_guncelle(eslesme)} post guncellendi")


if __name__ == "__main__":
    sys.exit(main())
