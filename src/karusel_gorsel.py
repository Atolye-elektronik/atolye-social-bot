"""Editoryal carousel slaytlarını HTML'den üretir.

`carousel_gorsel.py` (koyu lacivert, PIL ile çizilen) bu modülün yerini
almıyor — o hâlâ ürün fotoğrafı carousel'leri için duruyor. Bu modül, okul
fiyat listesi karuselinde oturan açık renkli editoryal düzeni üretiyor:
büyük serif başlık, üstte üç renkli şerit, altta ince çizgili altbilgi.

Neden PIL değil de HTML: bu düzende metin uzunluğu slayttan slayta değişiyor
ve satır sarma, dikey ortalama, kart yükseklikleri hep akışa bağlı. Bunları
PIL'de elle hesaplamak yerine tarayıcının yerleşim motoruna bırakmak hem
kısa hem de kırpma hatalarına kapalı.

Kullanımı:
    from src import karusel_gorsel as kg
    with kg.Cizer() as cizer:
        cizer.kanca("KANCA", "Başlık", "alt metin", cikti=yol, sayfa=(1, 5))
"""

from __future__ import annotations

import html
import pathlib

from playwright.sync_api import sync_playwright

STIL_YOLU = pathlib.Path("content/karusel_sablon/stil.css")

GENISLIK, YUKSEKLIK = 1080, 1350          # Instagram 4:5

SITE = "atolyeelektronik.com"

# Kanca bu uzunlugu asarsa punto bir kademe dusuruluyor; yoksa uc satiri
# gecip dikey ortalamayi bozuyor.
KANCA_UZUN_ESIK = 42


def _kacis(metin: str) -> str:
    return html.escape(str(metin), quote=False)


def _altbilgi(sol: str, sag: str) -> str:
    return f'<div class="foot"><span>{_kacis(sol)}</span><b>{_kacis(sag)}</b></div>'


def _sayfa_etiketi(sayfa: tuple[int, int] | None) -> str:
    if not sayfa:
        return ""
    return f"{sayfa[0]}/{sayfa[1]}"


class Cizer:
    """Tek tarayıcı açıp birden çok slayt üretir.

    Slayt başına tarayıcı açmak carousel üretimini gereksiz yere uzatıyordu
    (her açılış ~1 sn); tek oturumda hepsi saniyeler içinde çıkıyor.
    """

    def __init__(self, stil_yolu: pathlib.Path = STIL_YOLU) -> None:
        self._stil = stil_yolu.read_text(encoding="utf-8")
        self._pw = None
        self._tarayici = None
        self._sayfa = None

    def __enter__(self) -> "Cizer":
        self._pw = sync_playwright().start()
        self._tarayici = self._pw.chromium.launch()
        self._sayfa = self._tarayici.new_page(
            viewport={"width": GENISLIK, "height": YUKSEKLIK}
        )
        return self

    def __exit__(self, *_) -> None:
        if self._tarayici:
            self._tarayici.close()
        if self._pw:
            self._pw.stop()

    def _uret(self, govde: str, cikti) -> pathlib.Path:
        cikti = pathlib.Path(cikti)
        cikti.parent.mkdir(parents=True, exist_ok=True)
        belge = (
            '<!doctype html><meta charset="utf-8">'
            f"<style>{self._stil}</style>"
            f'<div class="bar"></div><div class="pad">{govde}</div>'
        )
        # networkidle: urun fotografi uzaktan geliyorsa yuklenmeden yakalamayalim.
        self._sayfa.set_content(belge, wait_until="networkidle")
        self._sayfa.screenshot(path=str(cikti))
        return cikti

    # --- slayt tipleri -----------------------------------------------------

    def kanca(self, kicker: str, baslik: str, alt: str, cikti,
              sayfa: tuple[int, int] | None = None) -> pathlib.Path:
        """Açılış slaydı. Tek işi var: kaydırmayı durdurmak."""
        uzun = " uzun" if len(baslik) > KANCA_UZUN_ESIK else ""
        govde = (
            f'<div class="orta kanca{uzun}">'
            f'<div class="kicker">{_kacis(kicker)}</div>'
            f"<h1>{_kacis(baslik)}</h1>"
            + (f'<div class="sub">{_kacis(alt)}</div>' if alt else "")
            + "</div>"
            + _altbilgi(SITE, "Kaydır →" if not sayfa else _sayfa_etiketi(sayfa))
        )
        return self._uret(govde, cikti)

    def liste(self, kicker: str, baslik: str, maddeler: list[str], cikti,
              alt_bilgi: str = "", sayfa: tuple[int, int] | None = None) -> pathlib.Path:
        """Madde madde anlatım. `**kalın**` işaretlemesi destekleniyor."""
        ogeler = "".join(f"<li>{_vurgu(m)}</li>" for m in maddeler)
        govde = (
            f'<div class="kicker">{_kacis(kicker)}</div>'
            f"<h2>{_kacis(baslik)}</h2>"
            f'<div class="orta"><ul>{ogeler}</ul></div>'
            + _altbilgi(alt_bilgi or SITE, _sayfa_etiketi(sayfa))
        )
        return self._uret(govde, cikti)

    def satirlar(self, kicker: str, baslik: str, alt: str, satirlar: list[dict], cikti,
                 alt_bilgi: str = "", sayfa: tuple[int, int] | None = None) -> pathlib.Path:
        """Fiyat/özellik tablosu. satırlar: {ad, aciklama, deger, birim, vurgu}."""
        kartlar = ""
        for s in satirlar:
            sinif = "row hi" if s.get("vurgu") else "row"
            kartlar += (
                f'<div class="{sinif}"><div>'
                f'<div class="n">{_kacis(s.get("ad", ""))}</div>'
                f'<div class="d">{_kacis(s.get("aciklama", ""))}</div></div><div>'
                f'<div class="p">{_kacis(s.get("deger", ""))}</div>'
                f'<div class="u">{_kacis(s.get("birim", ""))}</div></div></div>'
            )
        govde = (
            f'<div class="kicker">{_kacis(kicker)}</div>'
            f"<h2>{_kacis(baslik)}</h2>"
            + (f'<div class="sub">{_kacis(alt)}</div>' if alt else "")
            + f'<div class="rows-fill">{kartlar}</div>'
            + _altbilgi(alt_bilgi or SITE, _sayfa_etiketi(sayfa))
        )
        return self._uret(govde, cikti)

    def foto(self, kicker: str, baslik: str, gorsel: str, cikti,
             alt_bilgi: str = "", sayfa: tuple[int, int] | None = None) -> pathlib.Path:
        """Ürün fotoğrafı — editoryal çerçeve içinde, kırpılmadan."""
        govde = (
            f'<div class="kicker">{_kacis(kicker)}</div>'
            f"<h2>{_kacis(baslik)}</h2>"
            f'<div class="foto"><img src="{html.escape(gorsel, quote=True)}" alt=""></div>'
            + _altbilgi(alt_bilgi or SITE, _sayfa_etiketi(sayfa))
        )
        return self._uret(govde, cikti)

    def kapanis(self, kicker: str, baslik: str, maddeler: list[str], cikti,
                alt_bilgi: str = "", sayfa: tuple[int, int] | None = None) -> pathlib.Path:
        """Sipariş çağrısı. Listeden farkı: altta rozet ve WhatsApp satırı."""
        ogeler = "".join(f"<li>{_vurgu(m)}</li>" for m in maddeler)
        govde = (
            f'<div class="orta">'
            f'<div class="kicker">{_kacis(kicker)}</div>'
            f"<h2>{_kacis(baslik)}</h2>"
            f"<ul>{ogeler}</ul>"
            f'<div class="badge">{_kacis(alt_bilgi or "WhatsApp 0546 825 32 10")}</div>'
            "</div>"
            + _altbilgi(f"{SITE}/pages/okul-siparisi", _sayfa_etiketi(sayfa))
        )
        return self._uret(govde, cikti)


def _vurgu(metin: str) -> str:
    """`**kalın**` işaretlemesini <b> etiketine çevirir, gerisini kaçırır."""
    parcalar = _kacis(metin).split("**")
    # Tek sayıdaki parçalar yıldızlar arasında kalanlar.
    return "".join(p if i % 2 == 0 else f"<b>{p}</b>" for i, p in enumerate(parcalar))
