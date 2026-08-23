"""Trendyol müşteri sorularını takip eder.

Cevap bekleyen (WAITING_FOR_ANSWER) soruları çeker, her biri için basit bir
cevap taslağı önerir ve hepsini tek bir GitHub issue'da toplar (bu repo'nun
Issues sekmesi TY/HB sipariş takibiyle aynı gelen kutusudur).

Cevaplar panelden ELLE gönderilir — otomasyon asla müşteriye doğrudan cevap
yazmaz; issue'daki taslak kopyala-yapıştır kolaylığı içindir.

Kullanım:  python src/marketplaces/trendyol_sorular.py
CI:        pazaryeri-sync.yml içinde 2 saatte bir koşar.
"""

import json
from pathlib import Path

import requests

from trendyol_client import BASE_URL, SUPPLIER_ID, _auth_header
from issue_tracker import upsert_issue

STATE_DIR = Path(__file__).resolve().parents[2] / "state"
STATE_FILE = STATE_DIR / "trendyol_questions.json"
ISSUE_TITLE = "Trendyol: Cevap bekleyen müşteri soruları"
PANEL_URL = "https://partner.trendyol.com/product-questions/answered-waiting"


def get_questions(status="WAITING_FOR_ANSWER", page=0, size=50):
    url = f"{BASE_URL}/qna/sellers/{SUPPLIER_ID}/questions/filter"
    resp = requests.get(
        url, headers=_auth_header(),
        params={"status": status, "page": page, "size": size,
                "orderByField": "CreatedDate", "orderByDirection": "DESC"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def taslak_cevap(soru_metni, urun_adi):
    """Soru içeriğine göre kaba bir cevap taslağı öner (elle düzeltilir)."""
    s = (soru_metni or "").lower()
    ad = urun_adi or "ürünümüz"
    if any(k in s for k in ("kargo", "ne zaman gelir", "kaç günde", "teslim")):
        return ("Merhaba, siparişiniz aynı gün ya da en geç ertesi iş günü kargoya verilir; "
                "Türkiye genelinde teslimat genellikle 1-3 iş günü sürmektedir. İyi günler dileriz.")
    if any(k in s for k in ("stok", "var mı", "mevcut mu", "kaldı mı")):
        return (f"Merhaba, {ad} stoklarımızda mevcuttur; sipariş verebilirsiniz. İyi günler dileriz.")
    if any(k in s for k in ("uyum", "çalışır mı", "destekl", "arduino", "uno")):
        return (f"Merhaba, {ad} Arduino Uno ve muadil kartlarla uyumludur. "
                "Setlerimiz bağlantı şeması ve örnek kodla birlikte gönderilir; "
                "kurulumda takılırsanız satıcı sorularından bize ulaşabilirsiniz. İyi günler dileriz.")
    if any(k in s for k in ("pil", "batarya", "şarj")):
        return (f"Merhaba, {ad} için piller güvenlik nedeniyle pakete dahil değildir; "
                "ürün açıklamasında belirtilen pillerle çalışır. İyi günler dileriz.")
    if any(k in s for k in ("fatura", "kurumsal", "vergi")):
        return ("Merhaba, tüm siparişlerimizde e-arşiv fatura düzenlenmektedir; kurumsal fatura için "
                "sipariş notuna vergi bilgilerinizi ekleyebilirsiniz. İyi günler dileriz.")
    if any(k in s for k in ("iade", "değişim", "garanti")):
        return ("Merhaba, ürünlerimiz iade/değişim koşullarına uygundur ve garanti kapsamındadır; "
                "Trendyol üzerinden kolayca iade talebi oluşturabilirsiniz. İyi günler dileriz.")
    return (f"Merhaba, ilginiz için teşekkürler. {ad} hakkında sorunuzu aldık; "
            "— (elle doldur) —. İyi günler dileriz.")


def main():
    data = get_questions()
    sorular = data.get("content") or []
    STATE_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if not sorular:
        print("Cevap bekleyen soru yok.")
        upsert_issue(ISSUE_TITLE, "Şu anda cevap bekleyen müşteri sorusu yok. 🎉",
                     ["trendyol", "soru"], create_if_missing=False)
        return

    satirlar = [f"**{len(sorular)} soru cevap bekliyor.** Cevaplar panelden gönderilir: {PANEL_URL}", ""]
    for q in sorular:
        urun = q.get("productName") or "?"
        metin = (q.get("text") or "").strip()
        tarih = q.get("creationDate") or q.get("createdDate") or ""
        web_url = q.get("webUrl") or ""
        satirlar += [
            f"### {urun}",
            f"- **Soru:** {metin}",
            f"- **Tarih (ms):** {tarih}" + (f" · [ürün]({web_url})" if web_url else ""),
            f"- **Taslak cevap:** {taslak_cevap(metin, urun)}",
            "",
        ]
    upsert_issue(ISSUE_TITLE, "\n".join(satirlar), ["trendyol", "soru"])
    print(f"{len(sorular)} soru issue'ya yazıldı.")


if __name__ == "__main__":
    main()
