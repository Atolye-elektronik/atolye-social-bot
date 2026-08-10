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
import smtplib
import time
from email.message import EmailMessage

STATE_PATH = pathlib.Path("state/okul_gonderilen.json")
EK_DOSYA = pathlib.Path("pazarlama/atolye-elektronik-okul-fiyat-listesi.pdf")

# Gönderimler arası bekleme (saniye). Sağlayıcı sınırlarına takılmamak için.
BEKLEME = 8

KONU = "Meslek lisesi atölye malzemeleri — sınıf paketi fiyatları (2026-2027)"

GOVDE = """\
Sayın {hitap},

Atölye Elektronik olarak meslek liselerinin elektrik-elektronik, mekatronik ve
bilişim atölyelerine malzeme tedarik ediyoruz. 2026-2027 eğitim yılı fiyat
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
WhatsApp: {telefon}

İyi çalışmalar dilerim.

--
{imza_blok}{site} · {eposta} · {telefon}

Bu ileti, okulunuzun kurumsal adresine bir defaya mahsus tanıtım amacıyla
gönderilmiştir. Liste dışı kalmak için "çıkar" yazıp yanıtlamanız yeterlidir;
bir daha yazmayız.
"""


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


def mesaj_kur(okul: dict, gonderen: str, imza: str) -> EmailMessage:
    mesaj = EmailMessage()
    mesaj["Subject"] = KONU
    mesaj["From"] = f"Atölye Elektronik <{gonderen}>"
    mesaj["To"] = okul["eposta"]
    mesaj["Reply-To"] = gonderen
    # IMZA_ADI verilmemişse kendi adını iki kez yazmayalım.
    imza_blok = f"{imza}\nAtölye Elektronik\n" if imza else "Atölye Elektronik\n"

    # Okul listesi bölüm bilgisi vermiyor; ileti müdürlüğe gidiyor. Doğru kişiye
    # ulaşması için iletilmesini rica ediyoruz.
    yonlendirme = (
        ""
        if okul["bolum"]
        else "\nBu iletinin elektrik-elektronik, mekatronik ya da bilişim alan/atölye\n"
        "şefinize iletilmesini rica ederim."
    )

    mesaj.set_content(
        GOVDE.format(
            hitap=hitap_kur(okul),
            sayfa="https://atolyeelektronik.com/pages/okul-siparisi",
            site="atolyeelektronik.com",
            eposta=gonderen,
            telefon=os.environ.get("ILETISIM_TELEFON", "0546 825 32 10"),
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
) -> int:
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
    okullar = [o for o in okullari_oku(liste) if _ozet(o["eposta"]) not in gonderilmis]

    if limit:
        okullar = okullar[:limit]

    if not okullar:
        print("Gönderilecek yeni okul yok.")
        return 0

    if dry_run:
        print(f"[kuru] {len(okullar)} okula gidecekti. Örnek ilk mesaj:\n")
        print(f"Kime  : {okullar[0]['eposta']}")
        print(f"Konu  : {KONU}\n")
        print(mesaj_kur(okullar[0], gonderen, imza).get_body().get_content())
        return len(okullar)

    yeni_kayitlar: list[dict] = []
    basarili = 0

    with smtplib.SMTP(host, port, timeout=60) as sunucu:
        sunucu.starttls()
        sunucu.login(gonderen, parola)

        for sira, okul in enumerate(okullar, start=1):
            try:
                sunucu.send_message(mesaj_kur(okul, gonderen, imza))
            except smtplib.SMTPException as hata:
                # Tek bir adres patlarsa kampanyayı durdurma; sonrakine geç.
                print(f"  {sira}/{len(okullar)} atlandı ({okul['okul']}): {hata}")
                continue

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
    args = parser.parse_args()
    calistir(args.liste, args.dry_run, args.limit, args.bekleme)


if __name__ == "__main__":
    main()
