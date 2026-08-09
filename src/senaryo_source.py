"""Ürünlere göre senaryolu (hikaye kurgulu) carousel üretir.

Klasik carousel üründen fotoğraf gösterir; senaryolu carousel ise izleyiciyi
bir hikayenin içine çeker: tanıdık bir dert → hayal → çözüm olarak ürün →
sipariş çağrısı. Amaç, ürüne ihtiyacı olduğunu hissettirmek.

Akış (7-8 slide):
    1. kanca   — tanıdık bir soru/durum
    2. dert    — problemin derinleştirilmesi
    3. hayal   — "peki ya şöyle olsaydı?"
    4. çözüm   — ürünün sahneye girişi (kapak)
    5-6. ürün  — fotoğraflar
    7. kapanış — senaryoya uygun sipariş çağrısı

Şablonlar ürün adındaki anahtar kelimelere göre seçilir (robot, deney,
arduino, el aletleri, sensör...). Uymayan ürünler için genel maker
senaryosu kullanılır.

Kullanımı:
    python -m src.senaryo_source --count 2
    python -m src.senaryo_source --handle arduino-baslangic-seti
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib

from . import carousel_gorsel
from .shopify_source import STORE_URL, _slugify, fetch_products, ozet

STATE_PATH = pathlib.Path("state/senaryo_seen.json")
POSTS_DIR = pathlib.Path("posts")
MEDIA_DIR = pathlib.Path("posts/media/carousel")

MAX_URUN_FOTO = 2   # senaryoda hikaye on planda, fotograf az


SENARYOLAR = [
    {
        "anahtar": ["robot"],
        "kanca": {
            "etiket": "TANIDIK GELDİ Mİ?",
            "baslik": "Çocuğun ekrandan başını kaldırmıyor mu?",
            "metin": ["Tablet, telefon, oyunlar... Her gün aynı ekran süresi tartışması."],
        },
        "dert": {
            "etiket": "HERKES AYNI DERTTE",
            "baslik": "Yasaklamak işe yaramıyor.",
            "metin": [
                "Çünkü merak duygusu yönlendirilmek ister, bastırılmak değil.",
                "Ekranı kapatmak yetmez — yerine koyacak bir şey gerek.",
            ],
        },
        "hayal": {
            "etiket": "PEKİ YA ŞÖYLE OLSA?",
            "baslik": "Kendi robotunu kendisi yapsa?",
            "metin": [
                "Vidasını sıksa, kablosunu bağlasa, kodunu yüklese...",
                "O robot odada dolaşmaya başladığında kurduğu cümle:",
                "\"Bunu ben yaptım!\"",
            ],
        },
        "cozum_etiket": "İŞTE ÇÖZÜM",
        "kapanis_baslik": ["İlk robotuna", "bugün başlasın"],
        "kapanis_alt": "Kutudan çıkan her şey kurulum için hazır",
        "kanca_caption": "Ekran süresi tartışmalarına son 🤖",
    },
    {
        "anahtar": ["deney", "başlangıç", "baslangic", "temel"],
        "kanca": {
            "etiket": "İTİRAF ET",
            "baslik": "Elektroniğe başlamak istiyorsun ama...",
            "metin": ["Nereden başlayacağını bilmiyorsun, değil mi?"],
        },
        "dert": {
            "etiket": "HEP AYNI HİKAYE",
            "baslik": "Videolar karışık, listeler uzun.",
            "metin": [
                "Hangi direnç? Hangi kablo? Breadboard'un hangi deliği?",
                "Malzeme ararken hevesin kaçıyor, proje hiç başlamıyor.",
            ],
        },
        "hayal": {
            "etiket": "OYSA ÇOK KOLAY",
            "baslik": "Her şey tek kutuda gelseydi?",
            "metin": [
                "İlk devreni bu akşam kurabilirdin.",
                "LED'in ilk yandığı an — o his başka hiçbir şeyde yok.",
            ],
        },
        "cozum_etiket": "SENİ BEKLEYEN KUTU",
        "kapanis_baslik": ["İlk devreni", "bu hafta kur"],
        "kapanis_alt": "Başlamak için tek ihtiyacın bu set",
        "kanca_caption": "Elektroniğe başlamanın en kolay yolu ⚡",
    },
    {
        "anahtar": ["arduino", "proje", "kit"],
        "kanca": {
            "etiket": "MAKER'LAR BURAYA",
            "baslik": "Kafanda bir proje fikri var, değil mi?",
            "metin": ["Aylardır \"bir gün yapacağım\" diyorsun."],
        },
        "dert": {
            "etiket": "SORUN ŞU",
            "baslik": "Parçaları tek tek toplamak çile.",
            "metin": [
                "Sensör bir siteden, modül başka siteden, kablolar üçüncüden...",
                "Kargolar gelene kadar heves bitiyor.",
            ],
        },
        "hayal": {
            "etiket": "BİR DÜŞÜN",
            "baslik": "Hepsi aynı anda elinde olsaydı?",
            "metin": [
                "Bu hafta sonu prototipin çalışıyor olurdu.",
                "Fikir aşamasından çalışan projeye — tek kutu.",
            ],
        },
        "cozum_etiket": "TEK KUTUDA HEPSİ",
        "kapanis_baslik": ["Projeni", "hayata geçir"],
        "kapanis_alt": "Fikrin hazırsa malzemen de hazır",
        "kanca_caption": "O projeye başlamanın tam zamanı 🛠️",
    },
    {
        "anahtar": ["tornavida", "pense", "yankeski", "kargaburun", "havya", "takım", "alet", "çanta"],
        "kanca": {
            "etiket": "HİÇ BAŞINA GELDİ Mİ?",
            "baslik": "Tam iş bitecekken alet seni yarı yolda bıraktı.",
            "metin": ["Vida yalama oldu, uç büküldü, kablo düzgün kesilmedi..."],
        },
        "dert": {
            "etiket": "UCUZ ALET PAHALIYA PATLAR",
            "baslik": "Kötü alet hem işi hem malzemeyi bozar.",
            "metin": [
                "Bir kez yalama olan vida bir daha kolay sökülmez.",
                "Her seferinde baştan uğraşırsın.",
            ],
        },
        "hayal": {
            "etiket": "İŞİNİ SEVEN BİLİR",
            "baslik": "Doğru alet elinde başka duruyor.",
            "metin": [
                "Tak, sık, bitti. İş ilk seferde tamam.",
                "Yıllarca kullanacağın aletler çekmecende hazır.",
            ],
        },
        "cozum_etiket": "USTALARIN TERCİHİ",
        "kapanis_baslik": ["Alet çantanı", "tamamla"],
        "kapanis_alt": "Bir kere al, yıllarca kullan",
        "kanca_caption": "İşini ilk seferde bitiren aletler 🔧",
    },
    {
        "anahtar": ["sensör", "sensor", "modül", "modul", "motor", "lcd", "rfid", "buzzer", "röle", "role"],
        "kanca": {
            "etiket": "PROJEN Mİ YARIM KALDI?",
            "baslik": "Tek bir parça yüzünden proje bekliyor.",
            "metin": ["O modül olmadan devre tamamlanmıyor, biliyoruz."],
        },
        "dert": {
            "etiket": "EN KÖTÜSÜ",
            "baslik": "Yanlış parça almak.",
            "metin": [
                "Uyumsuz pin dizilimi, eksik dokümantasyon, çalışmayan klonlar...",
                "İki hafta bekle, gelen parça uymasın — olmaz.",
            ],
        },
        "hayal": {
            "etiket": "DOĞRUSU BURADA",
            "baslik": "Arduino uyumlu, test edilmiş, hazır.",
            "metin": [
                "Bağlantı şeması belli, örnek kodu internette bol.",
                "Taktığın gibi çalışır, projen kaldığı yerden devam eder.",
            ],
        },
        "cozum_etiket": "ARADIĞIN PARÇA",
        "kapanis_baslik": ["Projeni", "tamamla"],
        "kapanis_alt": "Arduino uyumlu, projene hazır",
        "kanca_caption": "Projeni tamamlayan parça burada 🔌",
    },
    {
        "anahtar": ["meslek", "lise", "temrin", "mesem"],
        "kanca": {
            "etiket": "ATÖLYE DERSİ YAKLAŞIYOR",
            "baslik": "Malzeme listesi elinde, kafan karışık mı?",
            "metin": ["Dönem başı telaşında eksik malzemeyle derse girmek istemezsin."],
        },
        "dert": {
            "etiket": "BİLİYORUZ",
            "baslik": "Tek tek toplamak hem pahalı hem yorucu.",
            "metin": [
                "Üç mağaza, beş kargo, yine de eksik çıkan parçalar...",
                "Üstelik yanlış malzeme alma riski hep var.",
            ],
        },
        "hayal": {
            "etiket": "RAHATLA",
            "baslik": "Müfredata uygun set hazır gelse?",
            "metin": [
                "Listedeki her şey tek kutuda, derse hazır.",
                "Sen sadece öğrenmeye odaklan.",
            ],
        },
        "cozum_etiket": "DERSE HAZIR SET",
        "kapanis_baslik": ["Döneme", "hazır başla"],
        "kapanis_alt": "Müfredata uygun, eksiksiz içerik",
        "kanca_caption": "Atölye dersine tam hazırlık 🎓",
    },
]

# hicbir anahtara uymayan urunler icin genel senaryo
VARSAYILAN = SENARYOLAR[2]


def senaryo_sec(product: dict) -> dict:
    metin = (product.get("title", "") + " " + product.get("handle", "")).lower()

    def oncelik(s: dict) -> int:
        # meslek lisesi setleri "takım/çanta" gibi genel kelimelerden önce
        if "meslek" in s["anahtar"]:
            return 0
        # tekil parçalarda (sette değilse) parça senaryosu "arduino"dan önce
        if "sensör" in s["anahtar"]:
            return 1 if "set" not in metin else 3
        return 2
    for senaryo in sorted(SENARYOLAR, key=oncelik):
        if any(a in metin for a in senaryo["anahtar"]):
            return senaryo
    return VARSAYILAN


def build_caption(product: dict, senaryo: dict) -> str:
    title = product.get("title", "").strip()
    description = ozet(product.get("body_html", ""), limit=180)

    lines = [senaryo["kanca_caption"], "", f"{senaryo['kanca']['baslik']}", "Cevabı carousel'de 👉 kaydır"]
    if description:
        lines += ["", f"⚡ {title}: {description}"]
    if product.get("handle"):
        lines += ["", f"Sipariş için \U0001f449 {STORE_URL}/products/{product['handle']}"]
    lines += ["", "\U0001f381 İlk alışverişine özel: ATOLYE10 koduyla sepette %10 indirim!"]
    lines += ["", "#atolyeelektronik #elektronik #arduino #maker #hobi #antalya"]
    return "\n".join(lines)


def build_slides(product: dict, senaryo: dict, slug: str) -> list[str]:
    klasor = MEDIA_DIR / slug
    title = product.get("title", "").strip()
    images = [img["src"] for img in product.get("images", [])][:MAX_URUN_FOTO]

    yollar: list[str] = []

    for i, ad in enumerate(("kanca", "dert", "hayal"), start=1):
        spec = senaryo[ad]
        yol = klasor / f"{i:02d}-{ad}.jpg"
        carousel_gorsel.metin(spec["etiket"], spec["baslik"], spec["metin"], yol)
        yollar.append(str(yol))

    yol = klasor / "04-cozum.jpg"
    carousel_gorsel.kapak(title, yol, alt_baslik=senaryo["cozum_etiket"])
    yollar.append(str(yol))

    for i, src in enumerate(images, start=1):
        yol = klasor / f"{i + 4:02d}-urun.jpg"
        carousel_gorsel.urun(src, title, sira=i, toplam=len(images), cikti=yol)
        yollar.append(str(yol))

    yol = klasor / f"{len(images) + 5:02d}-kapanis.jpg"
    carousel_gorsel.kapanis(yol, baslik_satirlari=senaryo["kapanis_baslik"],
                            alt_yazi=senaryo["kapanis_alt"])
    yollar.append(str(yol))

    return yollar


def _load_seen() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        return set(json.loads(STATE_PATH.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return set()


def _save_seen(seen: set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_post(product: dict, senaryo: dict, slug: str, slides: list[str],
               when: dt.datetime) -> pathlib.Path:
    path = POSTS_DIR / f"{slug}.md"
    media = "[" + ", ".join(slides) + "]"
    body = (
        "---\n"
        "platforms: [instagram, facebook]\n"
        f"media: {media}\n"
        f"publish_at: {when:%Y-%m-%d %H:%M}\n"
        "---\n"
        f"{build_caption(product, senaryo)}\n"
    )
    path.write_text(body, encoding="utf-8")
    return path


def generate(count: int = 2, start_in_hours: int = 24, spacing_hours: int = 48,
             handle: str | None = None) -> list[pathlib.Path]:
    seen = _load_seen()
    products = fetch_products()

    if handle:
        secilen = [p for p in products if p.get("handle") == handle]
        if not secilen:
            print(f"Ürün bulunamadı: {handle}")
            return []
    else:
        secilen = [
            p for p in products
            if str(p.get("id")) not in seen and (p.get("images") or [])
        ]
        # hikayesi guclu kategoriler (setler, kitler) one gelsin
        secilen.sort(key=lambda p: len(p.get("images") or []), reverse=True)

    if not secilen:
        print("Senaryo üretilecek yeni ürün bulunamadı.")
        return []

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    created: list[pathlib.Path] = []
    when = dt.datetime.now().astimezone() + dt.timedelta(hours=start_in_hours)

    for product in secilen[:count]:
        slug = f"{when:%Y-%m-%d}-senaryo-{_slugify(product.get('handle') or product.get('title', ''))}"
        path = POSTS_DIR / f"{slug}.md"
        if path.exists():
            when += dt.timedelta(hours=spacing_hours)
            continue

        senaryo = senaryo_sec(product)
        print(f"Senaryo üretiliyor: {product.get('title')} ({senaryo['kanca']['etiket']})")
        slides = build_slides(product, senaryo, slug)
        path = write_post(product, senaryo, slug, slides, when)
        created.append(path)
        seen.add(str(product["id"]))
        when += dt.timedelta(hours=spacing_hours)
        print(f"Oluşturuldu: {path} ({len(slides)} slide)")

    _save_seen(seen)
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Ürünlerden senaryolu carousel üret")
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--start-in-hours", type=int, default=24)
    parser.add_argument("--spacing-hours", type=int, default=48)
    parser.add_argument("--handle", help="Sadece bu ürün için üret (Shopify handle)")
    args = parser.parse_args()
    generate(args.count, args.start_in_hours, args.spacing_hours, handle=args.handle)


if __name__ == "__main__":
    main()
