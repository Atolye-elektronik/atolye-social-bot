"""DEVAM.md dosyasından HTML ve PDF sürümlerini üretir.

Devam notu elle iki yerde tutulmuyordu: `pazarlama/devam.html` ve
`pazarlama/devam-notu.pdf` daha önce elle yazılmıştı, o yüzden DEVAM.md her
güncellendiğinde bayatlıyorlardı. Bu betik ikisini de kaynaktan üretir.

Kullanımı:
    python -m playwright install chromium   # bir kez
    python tools/devam_pdf.py
"""

from __future__ import annotations

import pathlib

import markdown
from playwright.sync_api import sync_playwright

KOK = pathlib.Path(__file__).resolve().parent.parent
KAYNAK = KOK / "DEVAM.md"
HTML = KOK / "pazarlama/devam.html"
PDF = KOK / "pazarlama/devam-notu.pdf"

# Baskı için ayarlanmış stil: A4, kenar boşlukları ve sayfa bölünmesini
# bozmayacak page-break kuralları dahil.
STIL = """
@page { size: A4; margin: 16mm 15mm; }
* { box-sizing: border-box; }
body { font-family: "DejaVu Sans","Liberation Sans",Arial,sans-serif; font-size: 10pt;
  line-height: 1.55; color: #14100C; max-width: 100%; }
h1 { font-family: Georgia,"DejaVu Serif",serif; font-size: 23pt; letter-spacing:-.01em;
  border-bottom: 2.5pt solid #14100C; padding-bottom: 7pt; margin: 0 0 6pt; }
h2 { font-family: Georgia,"DejaVu Serif",serif; font-size: 15pt; margin: 20pt 0 7pt;
  padding-bottom: 3pt; border-bottom: 1pt solid #D8D0C6; color:#8E4A18;
  page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 13pt 0 5pt; page-break-after: avoid; }
p, li { margin: 0 0 6pt; }
ul, ol { padding-left: 17pt; margin-bottom: 8pt; }
strong { color: #8E4A18; }
code { font-family:"DejaVu Sans Mono",monospace; font-size: 8.8pt; background:#EFEBE4;
  padding: 1pt 3pt; border-radius: 2pt; color:#245043; }
pre { background:#F4F2ED; border:.8pt solid #D8D0C6; border-left:3pt solid #245043;
  border-radius:3pt; padding:8pt 10pt; overflow-x:auto; page-break-inside: avoid; }
pre code { background:none; padding:0; font-size:8.4pt; color:#14100C; line-height:1.45; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0 12pt; font-size: 9pt;
  page-break-inside: avoid; }
th { background:#245043; color:#fff; text-align:left; padding:5pt 7pt; font-size:8.6pt; }
td { padding:5pt 7pt; border-bottom:.6pt solid #E2DDD4; vertical-align: top; }
tr:nth-child(even) td { background:#FAF8F5; }
hr { border:0; border-top:1pt solid #D8D0C6; margin:16pt 0; }
blockquote { margin:6pt 0; padding:5pt 11pt; border-left:3pt solid #8E4A18;
  background:#F7F2EC; color:#4A423A; }
a { color:#245043; word-break: break-all; }
"""


def html_uret() -> str:
    govde = markdown.markdown(
        KAYNAK.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    # İlk h1 zaten belgenin başlığı; ayrıca <title> veriyoruz ki PDF üstbilgisi
    # dosya yolu yerine anlamlı bir ad göstersin.
    return (
        '<!doctype html><meta charset="utf-8">'
        "<title>Atölye Elektronik — Devam Notu</title>"
        f"<style>{STIL}</style>\n{govde}\n"
    )


def main() -> None:
    HTML.write_text(html_uret(), encoding="utf-8")
    print(f"yazıldı: {HTML.relative_to(KOK)}")

    with sync_playwright() as p:
        tarayici = p.chromium.launch()
        sayfa = tarayici.new_page()
        # networkidle: yerleşim oturmadan yakalamamak için (bölüm 7'deki tuzak).
        sayfa.goto(HTML.as_uri(), wait_until="networkidle")
        sayfa.pdf(path=str(PDF), format="A4", print_background=True)
        tarayici.close()

    print(f"yazıldı: {PDF.relative_to(KOK)}  ({PDF.stat().st_size:,} bayt)")


if __name__ == "__main__":
    main()
