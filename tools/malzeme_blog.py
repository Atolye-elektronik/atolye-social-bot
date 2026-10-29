"""content/malzeme_bilgi.json'dan "X nedir, ne işe yarar?" blog yazısı gövdesi üretir.

Sosyal medyadaki "Bu nedir?" serisiyle aynı içerik; blogda daha uzun ve
set linkleriyle. Çıktı Shopify articleCreate değişkenleri (JSON) — yazıyı
Admin API / MCP ile taslak (isPublished=false) olarak oluşturmak için.

    python tools/malzeme_blog.py l298n hcsr04 > blog.json
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import sys

KOK = pathlib.Path(__file__).resolve().parent.parent
ICERIK = KOK / "content" / "malzeme_bilgi.json"
SITE = "https://atolyeelektronik.com"

# Set kisa adi -> Shopify handle (malzeme_bilgi.json 'setler' alanindaki adlar).
SET_LINK = {
    "Çizgi İzleyen Robot Kiti": "cizgi-izleyen-robot-araba-kiti",
    "Engelden Kaçan Robot Kiti": "arduino-2wd-servolu-engelden-kacan-robot-araba-kiti-demonte-robot-araba-kiti",
    "Bluetooth Robot Kiti": "bluetooth-kontrollu-robot-kiti-2wd-robot-govde-hc-06-bluetooth-modulu",
    "IR Kumandalı Robot Kiti": "ir-kumandali-robot-araba-kiti-2wd-arduino-motor-surucu-kumanda",
    "3'ü 1 Arada Robot Kiti": "3u-1-arada-cok-fonksiyonlu-robot-araba-kiti-bluetooth-ir-kumanda-engelden-kacan",
    "Arduino Başlangıç Seti": "arduino-baslangic-seti",
    "Arduino Proje Seti (56 parça)": "arduino-proje-ve-uygulama-gelistirme-seti-56-parca",
    "Arduino İleri Seviye Set (88 parça)": "arduino-ileri-seviye-kutulu-egitim-seti-88-parca",
    "Akıllı Proje ve Sensör Seti": "akilli-proje-ve-sensor-modulleri-seti-10-parca",
    "RFID Kartlı Kilit Kiti": "rfid-kartli-akilli-kilit-sistemi-kiti-rc522-arduino-uno-servo-motor",
    "Sıcaklık-Nem Ekran Kiti": "sicaklik-nem-izleme-ekran-kiti-dht11-lcd-arduino",
    "Hareket Algılayan Alarm Kiti": "hareket-algilayan-alarm-sistemi-kiti-pir-role-arduino",
    "Dijital Saat Takvim Kiti": "dijital-saat-takvim-projesi-kiti-ds1302-lcd-arduino",
    "Step Motor Konumlandırma Kiti": "step-motor-ile-hassas-konumlandirma-kiti-28bjy-48-arduino",
    "Şarj Edilebilir Güç Seti": "sarj-edilebilir-guc-seti-tp4056-type-c-18650-tekli-pil-yuvasi",
    "Temel Elektronik Deney Seti": "temel-elektronik-deney-seti",
    "Endüstriyel Elektronik Uygulama Seti": "meslek-lisesi-11-sinif-endustriyel-elektronik-uygulama-seti",
    "Fen Deney Seti": "fen-deney-seti-breadboard-pil-kutusu-dc-motor-pervane-anahtar",
}

TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _slug(metin: str) -> str:
    s = metin.translate(TR).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _md(metin: str) -> str:
    """**kalin** -> <strong>, gerisi kacisli."""
    parca = html.escape(metin).split("**")
    return "".join(f"<strong>{p}</strong>" if i % 2 else p for i, p in enumerate(parca))


def _liste(maddeler: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{_md(m)}</li>" for m in maddeler) + "</ul>"


def govde(m: dict, gorsel: str | None = None) -> str:
    ad = html.escape(m["ad"])
    urun_link = f'{SITE}/products/{m["handle"]}'
    parcalar = [
        f"<p><em>{html.escape(m['soru'])}</em> {html.escape(m.get('alt', ''))}</p>",
        f"<p>Bu yazıda <strong>{ad}</strong> nedir, nasıl çalışır ve hangi projelerde "
        "kullanılır, kısaca anlatıyoruz. Meslek lisesi atölyesinde, TÜBİTAK projesinde "
        "ya da evde ilk Arduino denemende işine yarayacak.</p>",
    ]
    if gorsel:
        parcalar.append(f'<p><img src="{html.escape(gorsel, quote=True)}" alt="{ad}" '
                        'style="max-width:480px;width:100%"></p>')
    parcalar += [
        f"<h2>{ad} nedir?</h2>", _liste(m["nedir"]),
        "<h2>Nasıl çalışır?</h2>", _liste(m["nasil"]),
        "<h2>Hangi projelerde kullanılır?</h2>", _liste(m["projeler"]),
        "<h2>Hangi setlerde var?</h2>",
        "<p>Bu parça aşağıdaki setlerimizin içinde, bağlantı şeması ve örnek kodla birlikte geliyor:</p>",
        "<ul>" + "".join(
            f'<li><a href="{SITE}/products/{SET_LINK[s]}">{html.escape(s)}</a></li>'
            if s in SET_LINK else f"<li>{html.escape(s)}</li>"
            for s in m["setler"]
        ) + "</ul>",
        f'<p>Tek başına almak istersen: <a href="{urun_link}">{ad}</a>.</p>',
        "<p>Sorun olursa WhatsApp'tan yaz: <strong>0546 825 32 10</strong>.</p>",
    ]
    return "\n".join(parcalar)


def degiskenler(m: dict, blog_id: str, gorsel: str | None = None) -> dict:
    baslik = f"{m['ad']} Nedir, Ne İşe Yarar?"
    etiketler = [e.lstrip("#") for e in m.get("etiketler", "").split() if e.startswith("#")]
    etiketler = [e for e in etiketler if e not in ("atolyeelektronik",)]
    girdi = {
        "blogId": blog_id,
        "title": baslik,
        "handle": _slug(baslik),
        "author": {"name": "Atölye Elektronik"},
        "body": govde(m, gorsel),
        "summary": f"<p>{_md(m['nedir'][0])}. {html.escape(m.get('alt', ''))}</p>",
        "tags": ["bu nedir", "malzeme rehberi"] + etiketler,
        "isPublished": False,
    }
    if gorsel:
        girdi["image"] = {"url": gorsel, "altText": m["ad"]}
    return {"article": girdi}


def main() -> None:
    blog_id = "gid://shopify/Blog/103128727781"
    veri = json.loads(ICERIK.read_text(encoding="utf-8"))["malzemeler"]
    istenen = set(sys.argv[1:])
    cikti = [degiskenler(m, blog_id) for m in veri if not istenen or m["id"] in istenen]
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(cikti, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
