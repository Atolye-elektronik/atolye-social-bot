"""Terk edilmiş sepetleri izler ve mağaza sahibine hatırlatma e-postası atar.

Shopify'ın kendi "terk edilmiş ödeme" e-postası müşteriye otomatik gider ve
tek başına iyi iş görür. Ama toplu alım yapan öğretmen/okul sepetleri jenerik
bir hatırlatmayla dönmez: onların proforma fatura, havale bilgisi ya da
telefonla teyit gibi ihtiyaçları olur. Bu betik o sepetleri ayırıp sana
bildirir, sen de bizzat dönersin.

Müşteri adı, e-postası ve telefonu yalnızca sana giden e-postada yer alır.
Repoya, state dosyasına ve Actions loglarına asla yazılmaz — repo herkese
açık olduğu için bu ayrım önemli.

Kullanımı:
    python -m src.sepet_takip --dry-run     # kimseye e-posta gitmez
    python -m src.sepet_takip
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import smtplib
from email.message import EmailMessage

import requests

from . import config

STATE_PATH = pathlib.Path("state/sepet_bildirilen.json")

# Bu eşiklerden birini geçen sepet "toplu alım" sayılır ve öncelikli işaretlenir.
TOPLU_ADET = 10
TOPLU_TUTAR = 1500.0

# Kaç gün geriye bakılacağı. Daha eskisi için kişisel takip anlamını yitiriyor.
GERIYE_GUN = 14

SORGU = """
query($first: Int!, $query: String!) {
  abandonedCheckouts(first: $first, query: $query, sortKey: CREATED_AT, reverse: true) {
    nodes {
      id
      createdAt
      abandonedCheckoutUrl
      totalPriceSet { shopMoney { amount currencyCode } }
      customer { displayName email phone }
      billingAddress { city }
      lineItems(first: 50) { nodes { title quantity } }
    }
  }
}
"""


def _bildirilenleri_oku() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        return set(json.loads(STATE_PATH.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return set()


def _bildirilenleri_yaz(kimlikler: set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(sorted(kimlikler), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sepetleri_cek(geriye_gun: int = GERIYE_GUN) -> list[dict]:
    """Son N günde terk edilmiş, henüz siparişe dönmemiş sepetleri getirir."""
    if not (config.SHOPIFY_STORE and config.SHOPIFY_TOKEN):
        raise RuntimeError(
            "SHOPIFY_STORE ve SHOPIFY_ADMIN_TOKEN tanımlı değil; sepetler çekilemiyor."
        )

    baslangic = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=geriye_gun)).date()
    response = requests.post(
        f"https://{config.SHOPIFY_STORE}.myshopify.com"
        f"/admin/api/{config.SHOPIFY_API_VERSION}/graphql.json",
        headers={
            "X-Shopify-Access-Token": config.SHOPIFY_TOKEN,
            "Content-Type": "application/json",
        },
        json={"query": SORGU, "variables": {"first": 50, "query": f"created_at:>={baslangic}"}},
        timeout=60,
    )
    response.raise_for_status()
    govde = response.json()

    if govde.get("errors"):
        raise RuntimeError(f"Shopify sorgusu hata verdi: {govde['errors']}")

    return govde["data"]["abandonedCheckouts"]["nodes"]


def topluca_mi(sepet: dict) -> bool:
    """Öğretmen/okul siparişi olma ihtimali yüksek sepetleri ayırır."""
    kalemler = sepet["lineItems"]["nodes"]
    en_yuksek_adet = max((k["quantity"] for k in kalemler), default=0)
    tutar = float(sepet["totalPriceSet"]["shopMoney"]["amount"])
    return en_yuksek_adet >= TOPLU_ADET or tutar >= TOPLU_TUTAR


def _tutar_yaz(sepet: dict) -> str:
    tutar = float(sepet["totalPriceSet"]["shopMoney"]["amount"])
    return f"{tutar:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") + " ₺"


def _gun_farki(sepet: dict) -> int:
    olusma = dt.datetime.fromisoformat(sepet["createdAt"].replace("Z", "+00:00"))
    return (dt.datetime.now(dt.timezone.utc) - olusma).days


def sepet_metni(sepet: dict) -> str:
    """Tek bir sepeti e-posta gövdesi için okunur hale getirir."""
    musteri = sepet.get("customer") or {}
    adres = sepet.get("billingAddress") or {}

    satirlar = [
        f"{'★ TOPLU ALIM — ÖNCELİKLİ' if topluca_mi(sepet) else 'Tekil sepet'}",
        f"Tutar      : {_tutar_yaz(sepet)}",
        f"Bekleme    : {_gun_farki(sepet)} gün",
        f"Müşteri    : {musteri.get('displayName') or 'İsim yok'}",
        f"E-posta    : {musteri.get('email') or '—'}",
        f"Telefon    : {musteri.get('phone') or '—'}",
        f"Şehir      : {adres.get('city') or '—'}",
        "Sepet      :",
    ]
    for kalem in sepet["lineItems"]["nodes"]:
        satirlar.append(f"             {kalem['quantity']} × {kalem['title']}")
    satirlar.append(f"Kurtarma   : {sepet['abandonedCheckoutUrl']}")

    if topluca_mi(sepet):
        satirlar += [
            "",
            "  Önerilen mesaj:",
            "  Merhaba, Atölye Elektronik'ten yazıyorum. Sitemizden toplu bir sipariş",
            "  hazırlamışsınız ama tamamlanmamış. Okul ve kurum alımlarında proforma",
            "  fatura düzenliyor, havale/EFT ile ödeme alıyoruz; kredi kartı şart değil.",
            "  1.200 ₺ üzeri gönderilerde kargo bizden. Sınıf mevcudunuza göre adet ve",
            "  fiyat da ayarlayabiliriz. Yardımcı olmamı ister misiniz?",
        ]

    return "\n".join(satirlar)


def eposta_gonder(konu: str, govde: str) -> None:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    kullanici = os.environ.get("SMTP_USER", "").strip()
    parola = os.environ.get("SMTP_PASSWORD", "").strip()
    alici = os.environ.get("ALERT_EMAIL", "").strip() or kullanici

    if not (kullanici and parola and alici):
        raise RuntimeError(
            "SMTP_USER, SMTP_PASSWORD ve ALERT_EMAIL tanımlı olmalı. "
            "Gmail için hesap ayarlarından 'uygulama şifresi' üretip SMTP_PASSWORD'e koy."
        )

    mesaj = EmailMessage()
    mesaj["Subject"] = konu
    mesaj["From"] = kullanici
    mesaj["To"] = alici
    mesaj.set_content(govde)

    with smtplib.SMTP(host, port, timeout=60) as sunucu:
        sunucu.starttls()
        sunucu.login(kullanici, parola)
        sunucu.send_message(mesaj)


def calistir(dry_run: bool = False, geriye_gun: int = GERIYE_GUN) -> int:
    bildirilen = _bildirilenleri_oku()
    sepetler = sepetleri_cek(geriye_gun)

    yeni = [s for s in sepetler if s["id"] not in bildirilen]
    if not yeni:
        print(f"Son {geriye_gun} günde bildirilmemiş terk edilmiş sepet yok.")
        return 0

    # Toplu alımlar başa gelsin; sen listeye yukarıdan aşağı bakacaksın.
    yeni.sort(key=lambda s: (not topluca_mi(s), -float(s["totalPriceSet"]["shopMoney"]["amount"])))

    toplu_sayi = sum(1 for s in yeni if topluca_mi(s))
    toplam_tutar = sum(float(s["totalPriceSet"]["shopMoney"]["amount"]) for s in yeni)

    govde = "\n\n".join(
        [
            f"{len(yeni)} yeni terk edilmiş sepet var. Toplam {toplam_tutar:,.0f} ₺.".replace(",", "."),
            f"Bunlardan {toplu_sayi} tanesi toplu alım — muhtemelen öğretmen ya da okul.",
            "-" * 60,
        ]
        + [sepet_metni(s) + "\n" + "-" * 60 for s in yeni]
    )

    konu = f"[Atölye Elektronik] {len(yeni)} terk edilmiş sepet — {toplam_tutar:,.0f} ₺".replace(",", ".")

    if dry_run:
        # Kuru çalışmada bile müşteri bilgisi ekrana basılmaz; loglar herkese açık.
        print(f"[kuru] Gönderilecekti: {konu}")
        print(f"[kuru] {len(yeni)} sepet, {toplu_sayi} tanesi toplu alım.")
        return len(yeni)

    eposta_gonder(konu, govde)
    print(f"E-posta gönderildi: {len(yeni)} sepet, {toplu_sayi} tanesi toplu alım.")

    bildirilen.update(s["id"] for s in yeni)
    _bildirilenleri_yaz(bildirilen)
    return len(yeni)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Terk edilmiş sepetleri izler, toplu alımları öne çıkarır"
    )
    parser.add_argument("--dry-run", action="store_true", help="E-posta göndermeden dene")
    parser.add_argument("--gun", type=int, default=GERIYE_GUN, help="Kaç gün geriye bakılsın")
    args = parser.parse_args()
    calistir(dry_run=args.dry_run, geriye_gun=args.gun)


if __name__ == "__main__":
    main()
