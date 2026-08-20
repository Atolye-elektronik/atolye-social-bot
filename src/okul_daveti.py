"""Okullara kişiselleştirilmiş tanıtım e-postası gönderir.

Meslek liselerinin bölüm şefleri malzeme listesini eylülün ilk iki haftasında
kesinleştiriyor. Yüz yüze dolaşmaya vakit yoksa en hızlı yol, okulun sitesinde
zaten yayınlanmış kurumsal adrese tek sayfalık bir fiyat listesi göndermek.

Bu betik toplu gönderim yapar ama spam atmaz: her e-posta okul ve bölüm adıyla
kişiselleştirilir, altına çıkma (listeden çıkarma) satırı eklenir ve gönderimler
arasında bekleme konur. Aynı okula iki kez gitmemesi için gönderdiklerini
`state/okul_gonderilen.json` içinde tutar — oraya e-posta adresi değil, adresin
özeti (hash) yazılır.

Liste dosyası (`pazarlama/okullar.csv`) repoya girmez, `.gitignore` içindedir.

Kullanımı:
    python -m src.okul_daveti --liste pazarlama/okullar.csv --dry-run
    python -m src.okul_daveti --liste pazarlama/okullar.csv --limit 50
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import pathlib
import re
import imaplib
import smtplib
import time
from email.message import EmailMessage

STATE_PATH = pathlib.Path("state/okul_gonderilen.json")
EK_DOSYA = pathlib.Path("pazarlama/atolye-elektronik-okul-fiyat-listesi.pdf")

# Gönderimler arası bekleme (saniye). Sağlayıcı sınırlarına takılmamak için.
BEKLEME = 8

KONU = "Meslek lisesi atölye malzemeleri — sınıf paketi fiyatları (2026-2027)"

# MESEM ogrencisi atolyede degil isletmede egitim goruyor; temrin defteri,
# takim cantasi ve Arduino seti onlara uymuyor. Tek ilgili urun is dosyasi.
KONU_MESEM = "İşletmelerde Mesleki Eğitim İş Dosyası — sınıf paketi fiyatları (2026-2027)"

GOVDE = """\
Sayın {hitap},

Atölye Elektronik olarak meslek liselerinin elektrik-elektronik ve bilişim
atölyelerine malzeme tedarik ediyoruz. 2026-2027 eğitim yılı fiyat
listemizi ekte tek sayfa halinde gönderiyorum.
{yonlendirme}

Öğretmenlerin en çok sorduğu üç konu:

  • Proforma fatura düzenliyoruz — okul muhasebesi için sipariş öncesi hazırlanır.
  • Havale/EFT ile ödeme alıyoruz, kredi kartı zorunlu değil.
  • Sınıfın tamamı tek koli halinde doğrudan okul adresine gidiyor.

Sınıf paketi fiyatlarımız (temrin defteri ve işletmelerde mesleki eğitim iş dosyası):

  10 adet     833,00 ₺     (83,30 ₺/adet)
  20 adet   1.649,00 ₺     (82,45 ₺/adet, kargo bizden)
  30 adet   2.473,50 ₺     (82,45 ₺/adet, kargo bizden)

Tekli fiyat 85 ₺; 1.200 ₺ üzeri tüm gönderilerde kargo ücretsiz. Sınıf mevcudunuz
farklıysa (24, 32, 45 kişi) o adede göre de fiyat çıkarıyoruz.

Takım çantası setleri, Arduino eğitim setleri ve bitirme projesi kitleri de
listede yer alıyor.

Sınıf mevcudunuzu ve ihtiyaç listenizi yazmanız yeterli, aynı gün proforma
faturayla birlikte dönüş yapayım.

Koşulların tamamı: {sayfa}
WhatsApp: {wa_link}  ({telefon})

İyi çalışmalar dilerim.

--
{imza_blok}{site} · {eposta} · {telefon}

Bu ileti, okulunuzun kurumsal adresine bir defaya mahsus tanıtım amacıyla
gönderilmiştir. Liste dışı kalmak için "çıkar" yazıp yanıtlamanız yeterlidir;
bir daha yazmayız.
"""


ENV_DOSYA = pathlib.Path(".env")


def _env_dosyasini_yukle() -> None:
    """Varsa `.env` dosyasındaki değerleri ortama alır.

    Gmail uygulama şifresini terminalde ortam değişkeni olarak vermek herkes
    için pratik değil (PowerShell'de tırnak/kaçış hataları, `setx`in kayıt
    defterine düz metin yazması). Bunun yerine şifre `.env` dosyasına
    yazılabiliyor; dosya `.gitignore` içinde, repoya girmiyor.

    Ortamda zaten tanımlı olan değişkenler ezilmez — CI'da CI değişkenleri
    geçerli kalsın diye.
    """
    if not ENV_DOSYA.exists():
        return

    for satir in ENV_DOSYA.read_text(encoding="utf-8-sig").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        anahtar, _, deger = satir.partition("=")
        anahtar = anahtar.strip()
        # Değeri tırnak içinde yazanlar için; Not Defteri'nden yapıştırırken
        # tırnak koymak yaygın bir alışkanlık.
        deger = deger.strip().strip('"').strip("'")
        if anahtar and anahtar not in os.environ:
            os.environ[anahtar] = deger



GOVDE_MESEM = """Sayın {hitap},

Atölye Elektronik olarak mesleki eğitim merkezlerine İşletmelerde Mesleki
Eğitim İş Dosyası (staj defteri) tedarik ediyoruz. Milli Eğitim Bakanlığı
müfredatına ve güncel staj yönetmeliğine uyumlu, A4, tel dikişli.
{yonlendirme}

Sınıf paketi fiyatlarımız:

  10 adet     833,00 ₺     (83,30 ₺/adet)
  20 adet   1.649,00 ₺     (82,45 ₺/adet, kargo bizden)
  30 adet   2.473,50 ₺     (82,45 ₺/adet, kargo bizden)

Tekli fiyat 85 ₺; 1.200 ₺ üzeri tüm gönderilerde kargo ücretsiz. Öğrenci
sayınız farklıysa (24, 32, 45 kişi) o adede göre de fiyat çıkarıyoruz.

  • Proforma fatura düzenliyoruz — kurum muhasebesi için sipariş öncesi hazırlanır.
  • Havale/EFT ile ödeme alıyoruz, kredi kartı zorunlu değil.
  • Tamamı tek koli halinde doğrudan kurum adresine gidiyor.

Öğrenci sayınızı yazmanız yeterli, aynı gün proforma faturayla birlikte
dönüş yapayım.

Koşulların tamamı: {sayfa}
WhatsApp: {wa_link}  ({telefon})

İyi çalışmalar dilerim.

--
{imza_blok}{site} · {eposta} · {telefon}

Bu ileti, kurumunuzun kurumsal adresine bir defaya mahsus tanıtım amacıyla
gönderilmiştir. Liste dışı kalmak için "çıkar" yazıp yanıtlamanız yeterlidir;
bir daha yazmayız.
"""

# Sablon adi -> (konu, govde). Varsayilan MTAL'e gore yazilmis metin.
SABLONLAR = {
    "mtal": (KONU, GOVDE),
    "mesem": (KONU_MESEM, GOVDE_MESEM),
}

def _gonderilenleri_oku() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        kayit = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return {k["ozet"] for k in kayit}
    except (json.JSONDecodeError, KeyError, TypeError):
        return set()


def _gonderilenleri_yaz(kayitlar: list[dict]) -> None:
    mevcut: list[dict] = []
    if STATE_PATH.exists():
        try:
            mevcut = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            mevcut = []

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(mevcut + kayitlar, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _ozet(eposta: str) -> str:
    """E-posta adresinin geri döndürülemez özeti; repoya adres yazmamak için."""
    return hashlib.sha256(eposta.strip().lower().encode("utf-8")).hexdigest()[:16]


def okullari_oku(yol: pathlib.Path) -> list[dict]:
    """CSV sütunları: okul, eposta, bolum (bolum boş bırakılabilir)."""
    with yol.open(encoding="utf-8-sig", newline="") as dosya:
        satirlar = list(csv.DictReader(dosya))

    okullar = []
    for satir in satirlar:
        eposta = (satir.get("eposta") or "").strip()
        okul = (satir.get("okul") or "").strip()
        if not eposta or "@" not in eposta or not okul:
            continue
        okullar.append({"okul": okul, "eposta": eposta, "bolum": (satir.get("bolum") or "").strip()})
    return okullar


def hitap_kur(okul: dict) -> str:
    if okul["bolum"]:
        return f"{okul['okul']} {okul['bolum']} Bölüm Şefliği"
    return f"{okul['okul']} Müdürlüğü"


def mesaj_kur(okul: dict, gonderen: str, imza: str, sablon: str = "mtal") -> EmailMessage:
    konu, govde = SABLONLAR[sablon]
    mesaj = EmailMessage()
    mesaj["Subject"] = konu
    mesaj["From"] = f"Atölye Elektronik <{gonderen}>"
    mesaj["To"] = okul["eposta"]
    mesaj["Reply-To"] = gonderen
    telefon = os.environ.get("ILETISIM_TELEFON", "0546 825 32 10")

    # IMZA_ADI verilmemişse kendi adını iki kez yazmayalım.
    imza_blok = f"{imza}\nAtölye Elektronik\n" if imza else "Atölye Elektronik\n"

    # Liste bölüm bilgisi vermiyor; ileti müdürlüğe gidiyor. Doğru kişiye
    # ulaşması için iletilmesini rica ediyoruz. MESEM'de alan/atölye şefi
    # kadrosu yok — orada muhatap koordinatör.
    if okul["bolum"]:
        yonlendirme = ""
    elif sablon == "mesem":
        yonlendirme = (
            "\nBu iletinin işletmelerde mesleki eğitimden sorumlu\n"
            "koordinatörünüze iletilmesini rica ederim."
        )
    else:
        yonlendirme = (
            "\nBu iletinin elektrik-elektronik ya da bilişim alan/atölye şefinize\n"
            "iletilmesini rica ederim."
        )

    mesaj.set_content(
        govde.format(
            hitap=hitap_kur(okul),
            sayfa="https://atolyeelektronik.com/pages/okul-siparisi",
            site="atolyeelektronik.com",
            eposta=gonderen,
            telefon=telefon,
            wa_link="https://wa.me/9" + re.sub(r"\D", "", telefon),
            imza_blok=imza_blok,
            yonlendirme=yonlendirme,
        )
    )

    if EK_DOSYA.exists():
        tur, _ = mimetypes.guess_type(EK_DOSYA.name)
        ana, alt = (tur or "application/pdf").split("/", 1)
        mesaj.add_attachment(
            EK_DOSYA.read_bytes(),
            maintype=ana,
            subtype=alt,
            filename="Atolye-Elektronik-Okul-Fiyat-Listesi.pdf",
        )

    return mesaj


def calistir(
    liste: pathlib.Path,
    dry_run: bool = False,
    limit: int | None = None,
    bekleme: int = BEKLEME,
    sablon: str = "mtal",
    force: bool = False,
) -> int:
    _env_dosyasini_yukle()

    gonderen = os.environ.get("SMTP_USER", "").strip()
    parola = os.environ.get("SMTP_PASSWORD", "").strip()
    imza = os.environ.get("IMZA_ADI", "").strip()
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))

    if not dry_run and not (gonderen and parola):
        raise RuntimeError(
            "SMTP_USER ve SMTP_PASSWORD tanımlı olmalı. Gmail için hesap "
            "ayarlarından 'uygulama şifresi' üret."
        )
    gonderen = gonderen or "ornek@atolyeelektronik.com"

    if not EK_DOSYA.exists():
        print(f"Uyarı: {EK_DOSYA} bulunamadı, e-postalar eksiz gidecek.")

    gonderilmis = _gonderilenleri_oku()
    if force:
        # Yeniden gonderim: gmail.com doneminden gidenlerin spam'e dustugu
        # suphesiyle ayni okullara info@ uzerinden tekrar gidiliyor. Kayit
        # filtresi atlanir; okullar zaten kayitli oldugundan sonda tekrar
        # yazilmaz (mukerrer hash birikmesin).
        okullar = okullari_oku(liste)
    else:
        okullar = [o for o in okullari_oku(liste) if _ozet(o["eposta"]) not in gonderilmis]

    if limit:
        okullar = okullar[:limit]

    if not okullar:
        print("Gönderilecek yeni okul yok.")
        return 0

    if dry_run:
        print(f"[kuru] {len(okullar)} okula gidecekti. Örnek ilk mesaj:\n")
        print(f"Kime  : {okullar[0]['eposta']}")
        print(f"Konu  : {SABLONLAR[sablon][0]}\n")
        print(mesaj_kur(okullar[0], gonderen, imza, sablon).get_body().get_content())
        return len(okullar)

    yeni_kayitlar: list[dict] = []
    basarili = 0

    # Gonderilen her iletinin kopyasi sunucunun Sent klasorune yazilir.
    # SMTP gonderimi Gmail'den gecmedigi icin hicbir "Gonderilmis" klasorunde
    # iz birakmiyordu; kullanici gonderimin yapildigini goremiyordu.
    imap_baglanti = None
    try:
        imap_baglanti = imaplib.IMAP4_SSL(host, 993)
        imap_baglanti.login(gonderen, parola)
    except Exception as hata:
        print(f"Uyari: Sent kopyasi icin IMAP acilamadi ({hata}); gonderime devam.")
        imap_baglanti = None

    # 465 dogrudan SSL ister (starttls degil). Guzel Hosting'in 587'si art arda
    # baglantida selamlama gondermeyip zaman asimina dusebiliyor; 465 stabil.
    if port == 465:
        sunucu_baglanti = smtplib.SMTP_SSL(host, port, timeout=60)
    else:
        sunucu_baglanti = smtplib.SMTP(host, port, timeout=60)
    with sunucu_baglanti as sunucu:
        if port != 465:
            sunucu.starttls()
        sunucu.login(gonderen, parola)

        for sira, okul in enumerate(okullar, start=1):
            try:
                sunucu.send_message(mesaj_kur(okul, gonderen, imza, sablon))
            except smtplib.SMTPException as hata:
                # Tek bir adres patlarsa kampanyayı durdurma; sonrakine geç.
                print(f"  {sira}/{len(okullar)} atlandı ({okul['okul']}): {hata}")
                continue

            if imap_baglanti is not None:
                try:
                    imap_baglanti.append(
                        "INBOX.Sent", r"\Seen",
                        imaplib.Time2Internaldate(time.time()), mesaj.as_bytes()
                    )
                except Exception:
                    pass  # kopya dusmezse gonderim yine gecerli
            basarili += 1
            yeni_kayitlar.append({"okul": okul["okul"], "ozet": _ozet(okul["eposta"])})
            print(f"  {sira}/{len(okullar)} gönderildi: {okul['okul']}")

            if sira < len(okullar):
                time.sleep(bekleme)

    _gonderilenleri_yaz(yeni_kayitlar)
    print(f"\nToplam {basarili} okula gönderildi.")
    return basarili


def main() -> None:
    parser = argparse.ArgumentParser(description="Okullara tanıtım e-postası gönder")
    parser.add_argument("--liste", type=pathlib.Path, default=pathlib.Path("pazarlama/okullar.csv"))
    parser.add_argument("--dry-run", action="store_true", help="Göndermeden dene")
    parser.add_argument("--limit", type=int, help="En fazla kaç okula gönderilsin")
    parser.add_argument("--bekleme", type=int, default=BEKLEME, help="Gönderimler arası saniye")
    parser.add_argument("--force", action="store_true",
                        help="Kayıt filtresini atla (yeniden gönderim); kayda da yazmaz")
    parser.add_argument("--sablon", choices=sorted(SABLONLAR), default="mtal",
                        help="mesem: yalnızca iş dosyası anlatan metin")
    args = parser.parse_args()
    calistir(args.liste, args.dry_run, args.limit, args.bekleme, args.sablon, args.force)


if __name__ == "__main__":
    main()
