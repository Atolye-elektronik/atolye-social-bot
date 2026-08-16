"""TikTok Studio analitiğini çekip repoda tarihsel olarak biriktirir.

TikTok'un analitik uçları belgelenmiş değil. İki yoldan okuyoruz:

  1. Ağ dinleme (asıl yol) — sayfa açılırken kendi arka plan isteklerini
     yapıyor; cevapları yakalayıp içindeki sayıları çıkarıyoruz. Arayüz
     değişse bile bu yol genelde çalışmaya devam ediyor.

  2. DOM okuma (yedek) — ağdan bir şey çıkmazsa ekrandaki kartların
     metnini okuyoruz.

Sonuç state/tiktok_analytics.json içinde gün gün birikir; üzerine yazmaz,
böylece zamanla kendi geçmişin oluşur.

    python -m src.tiktok_studio analitik
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib

from . import selectors
from .session import LOG_DIR, bekle, dokum, studio

KAYIT = pathlib.Path("state/tiktok_analytics.json")

# Ağ cevaplarında aradığımız alan adları → rapordaki karşılıkları.
#
# Gerçek uçlar (/aweme/v2/data/insight/) genel bakış toplamlarını
# göndermiyor; onları tarayıcı günlük geçmişlerden kendisi hesaplıyor ve
# geçmiş dizileri çoğu istekte null geliyor. Ağdan güvenilir şekilde gelen
# sadece şu ikisi — gerisi ekrandan okunuyor.
METRIKLER: dict[str, tuple[str, ...]] = {
    "takipci": ("follower_num", "follower_count", "followers"),
    "tekil_izleyici": ("unique_viewer_num", "unique_viewers"),
}

# Ekrandaki kartların etiketleri. Sayı, etiketin bulunduğu kartın içinden
# okunuyor; sınıf adları (css-nr4if0 gibi) her yayında değiştiği için
# onlara değil metne bağlanıyoruz.
KART_ETIKETLERI: dict[str, tuple[str, ...]] = {
    "goruntulenme": ("Video Görüntülemeleri", "Video views"),
    "profil_goruntulenme": ("Profil Görüntülemeleri", "Profile views"),
    "begeni": ("Beğeniler", "Likes"),
    "yorum": ("Yorumlar", "Comments"),
    "paylasim": ("Paylaşımlar", "Shares"),
}

# Etiketi bulup kartın içindeki sayıyı çıkaran tarayıcı tarafı okuyucu.
KART_OKUYUCU_JS = r"""
(etiketler) => {
  const sonuc = {};
  for (const [anahtar, adlar] of Object.entries(etiketler)) {
    let bulundu = null;
    for (const ad of adlar) {
      const hedef = ad.toLowerCase();
      const yapraklar = [...document.querySelectorAll('div,span,p,h1,h2,h3,h4')].filter(
        e => e.children.length === 0 && e.textContent.trim().toLowerCase() === hedef
      );
      // Aynı metin birden fazla yerde olabiliyor (sol menüde de "Yorumlar"
      // var), o yüzden sayı verene kadar hepsini deniyoruz.
      for (const aday of yapraklar) {
        let kok = aday;
        for (let i = 0; i < 4 && kok.parentElement; i++) {
          kok = kok.parentElement;
          const kalan = (kok.innerText || '').replace(new RegExp(ad, 'i'), '');
          // Kartta önce büyük değer, altında "+16 (8.6%)" gibi değişim var;
          // kendi satırında duran ilk sayı aradığımız değer.
          const m = kalan.match(/(?:^|\n)\s*([\d.,]+\s?[KMB]?)\s*(?:\n|$)/);
          if (m) { bulundu = m[1].trim(); break; }
        }
        if (bulundu) break;
      }
      if (bulundu) break;
    }
    sonuc[anahtar] = bulundu;
  }
  return sonuc;
}
"""


def _sayiya_cevir(ham: str) -> int | None:
    """'12.4K' / '1,2 Mn' / '3.456' gibi metinleri sayıya çevirir.

    Ayırıcının anlamı çarpanın varlığına bağlı: '12.4K' bin ikili (12400),
    ama çarpansız '12.456' binlik gruplama (12456). Türkçe arayüzde virgül
    ondalık, 'B' bin ve 'Mn' milyon anlamına geliyor.
    """
    metin = ham.strip().lower().replace(" ", "").replace(" ", "")
    carpan = 1
    for son, kat in (("mn", 1_000_000), ("m", 1_000_000), ("k", 1_000), ("b", 1_000)):
        if metin.endswith(son):
            carpan = kat
            metin = metin[: -len(son)]
            break

    if carpan > 1:
        # Çarpan varsa son ayırıcı ondalıktır, öncekiler gruplama.
        metin = metin.replace(",", ".")
        if metin.count(".") > 1:
            bas, _, kuyruk = metin.rpartition(".")
            metin = bas.replace(".", "") + "." + kuyruk
    else:
        metin = metin.replace(".", "").replace(",", "")

    try:
        return int(float(metin) * carpan)
    except ValueError:
        return None


# Sarmalanmış metriklerde sayının bulunduğu alan adları.
SAYI_ALANLARI = ("value", "count", "total", "num", "sum")


def _icteki_sayi(dugum) -> int | None:
    """`{"value": 12045}` gibi sarmalanmış metrikten sayıyı çıkarır.

    TikTok aynı metriği bazen düz sayı, bazen tek alanlı bir sözlük olarak
    gönderiyor; sözlük halinde gelen değerler bu olmadan sessizce kayboluyordu.
    """
    if not isinstance(dugum, dict):
        return None
    for ad in SAYI_ALANLARI:
        deger = dugum.get(ad)
        if isinstance(deger, (int, float)) and not isinstance(deger, bool):
            return int(deger)
    return None


def _metrik_topla(dugum, bulunan: dict[str, int]) -> None:
    """JSON cevabının içinde gezip tanıdığı sayıları toplar."""
    if isinstance(dugum, dict):
        for anahtar, deger in dugum.items():
            ad = str(anahtar).lower()
            hedefler = [h for h, adlar in METRIKLER.items() if ad in adlar]

            if isinstance(deger, (int, float)) and not isinstance(deger, bool):
                for hedef in hedefler:
                    bulunan.setdefault(hedef, int(deger))
                continue

            if hedefler:
                icteki = _icteki_sayi(deger)
                if icteki is not None:
                    for hedef in hedefler:
                        bulunan.setdefault(hedef, icteki)
                    continue

            _metrik_topla(deger, bulunan)
    elif isinstance(dugum, list):
        for oge in dugum:
            _metrik_topla(oge, bulunan)


def _domdan_oku(page) -> dict[str, int]:
    """Genel bakış kartlarındaki sayıları ekrandan okur."""
    bulunan: dict[str, int] = {}
    try:
        ham = page.evaluate(KART_OKUYUCU_JS, {k: list(v) for k, v in KART_ETIKETLERI.items()})
    except Exception:  # noqa: BLE001 - sayfa henüz hazır değilse
        return bulunan

    for anahtar, metin in (ham or {}).items():
        if not metin:
            continue
        deger = _sayiya_cevir(metin)
        if deger is not None:
            bulunan[anahtar] = deger
    return bulunan


def topla() -> dict:
    """Studio analitiğini okur ve normalleştirilmiş bir sözlük döndürür."""
    ham_cevaplar: list[dict] = []
    yakalanan = []

    with studio(selectors.ANALITIK) as page:
        # Dikkat: response.json() olay işleyicisinin içinde çağrılırsa gövde
        # hemen gelmiyor, kayıtlar biz listeyi okuduktan sonra doluyordu ve
        # ağ metrikleri sessizce kaybediyordu. Bu yüzden işleyicide sadece
        # yanıtı biriktiriyor, gövdeleri aşağıda akışın içinde okuyoruz.
        def _yakala(response):
            if any(p in response.url for p in selectors.ANALITIK_ISTEK_PARCALARI):
                yakalanan.append(response)

        page.on("response", _yakala)

        # Sayfa açıldıktan sonra istekleri kendisi yapıyor; biraz bekle ve
        # grafikleri tetiklemek için aşağı kaydır.
        page.reload(wait_until="domcontentloaded")
        bekle(8)
        page.mouse.wheel(0, 1200)
        bekle(4)

        for yanit in list(yakalanan):
            try:
                ham_cevaplar.append({"url": yanit.url, "veri": yanit.json()})
            except Exception:  # noqa: BLE001 - JSON olmayan ya da boş cevaplar
                pass

        # İki kaynak birbirini tamamlıyor: takipçi ve tekil izleyici sayısı
        # ağ cevaplarında hazır geliyor, genel bakış toplamları ise sadece
        # ekranda (tarayıcı onları günlük geçmişlerden kendisi hesaplıyor).
        agdan: dict[str, int] = {}
        for cevap in ham_cevaplar:
            _metrik_topla(cevap["veri"], agdan)

        domdan = _domdan_oku(page)

        bulunan = {**agdan, **domdan}
        kaynak = "+".join(k for k, v in (("ag", agdan), ("dom", domdan)) if v) or "yok"

        if not bulunan:
            dokum(page, "analitik-bos")
            raise RuntimeError(
                "Analitik verisi okunamadı — ne ağ cevaplarında ne ekranda sayı bulundu. "
                f"Döküm: {LOG_DIR}/"
            )

    if ham_cevaplar:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (LOG_DIR / "analitik-ham.json").write_text(
            json.dumps(ham_cevaplar, ensure_ascii=False, indent=2)[:2_000_000],
            encoding="utf-8",
        )

    bulunan["kaynak"] = kaynak
    return bulunan


def kaydet(veri: dict) -> pathlib.Path:
    """Günün ölçümünü geçmişin üstüne ekler."""
    gecmis: dict = {}
    if KAYIT.exists():
        try:
            gecmis = json.loads(KAYIT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            gecmis = {}

    gunler = gecmis.setdefault("gunluk", {})
    bugun = dt.date.today().isoformat()
    gunler[bugun] = veri
    gecmis["guncelleme"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    KAYIT.parent.mkdir(parents=True, exist_ok=True)
    KAYIT.write_text(
        json.dumps(gecmis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return KAYIT


def calistir() -> int:
    veri = topla()
    yol = kaydet(veri)

    print("TikTok Studio analitiği:")
    for anahtar, deger in veri.items():
        if anahtar == "kaynak":
            continue
        print(f"  {anahtar:22} {deger:>12,}".replace(",", "."))
    print(f"\nKaydedildi: {yol} (kaynak: {veri.get('kaynak')})")
    return 0
